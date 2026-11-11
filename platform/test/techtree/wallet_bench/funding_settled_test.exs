defmodule Techtree.WalletBench.FundingSettledTest do
  # An unknown send is settled from Base, whose address can answer each read from a different node, some behind
  # others. Only a receipt, or a read pinned to one block, may decide; a send that landed is never taken as replaced.
  use Techtree.DataCase, async: false
  use ExUnitProperties

  alias Techtree.Actors.Operator
  alias Techtree.WalletBench
  alias Techtree.WalletBench.{Attempt, BaseRpc, Funding, Payment}

  @funder "0x00000000000000000000000000000000000f0bde"
  @stranger "0x00000000000000000000000000000000000a11ce"
  @hash "0x" <> String.duplicate("ab", 32)
  @other "0x" <> String.duplicate("cd", 32)
  @nonce 7

  setup do
    previous = Application.get_env(:techtree, WalletBench)

    Application.put_env(
      :techtree,
      WalletBench,
      Keyword.put(previous, :req_options, plug: {Req.Test, __MODULE__})
    )

    on_exit(fn -> Application.put_env(:techtree, WalletBench, previous) end)
  end

  test "a receipt decides at once" do
    node = base(receipts: [receipt("0x1", 640)], latest: 1_000, passed: 640)
    assert Funding.settled(payment()) == {:ok, {:confirmed, 640}}
    assert methods(node) == ["eth_getTransactionReceipt"]

    base(receipts: [receipt("0x0", 640)], latest: 1_000, passed: 640)
    assert Funding.settled(payment()) == {:ok, {:reverted, 640}}
  end

  test "no receipt, and the nonce unused at the finalized block: the send stays unknown" do
    node = base(receipts: [nil], latest: 1_000, passed: nil)
    assert {:error, error} = Funding.settled(payment())
    assert error =~ "was still unused at Base's finalized block 1000"
    assert count_blocks(node) == [1_000]
  end

  test "a lagging node with no receipt: the pinned search finds the send in its block, and its receipt decides" do
    node =
      base(
        receipts: [nil, receipt("0x1", 640)],
        latest: 1_000,
        passed: 640,
        blocks: %{
          640 => [
            transaction(@other, @stranger, @nonce),
            transaction(@other, @funder, @nonce - 1),
            transaction(String.upcase(@hash), @funder, @nonce)
          ]
        }
      )

    assert Funding.settled(payment()) == {:ok, {:confirmed, 640}}

    assert length(count_blocks(node)) ==
             Enum.count(methods(node), &(&1 == "eth_getTransactionCount"))

    assert Enum.all?(count_blocks(node), &(&1 <= 1_000))
    assert {"eth_getBlockByNumber", [BaseRpc.hex(640), true]} in calls(node)
  end

  test "another of the funder's transactions at the send's nonce: replaced" do
    base(
      receipts: [nil],
      latest: 1_000,
      passed: 640,
      blocks: %{
        640 => [transaction(@hash, @stranger, @nonce), transaction(@other, @funder, @nonce)]
      }
    )

    assert Funding.settled(payment()) == {:ok, :replaced}
  end

  test "in its block, but no node answering has its receipt yet: the send stays unknown" do
    base(
      receipts: [nil, nil],
      latest: 1_000,
      passed: 640,
      blocks: %{640 => [transaction(@hash, @funder, @nonce)]}
    )

    assert {:error, error} = Funding.settled(payment())
    assert error =~ "landed in Base's block 640, but Base has no receipt for it yet"
  end

  test "a lagging node without the pinned block refuses, and the send stays unknown" do
    base(receipts: [nil], latest: 1_000, head: 990, passed: 640)
    assert {:error, error} = Funding.settled(payment())
    assert error == "Base RPC eth_getTransactionCount answered 200 with error -32000"
  end

  test "nodes that disagree about the first block end the search, and the send stays unknown" do
    node = base(receipts: [nil], latest: 4, passed: 2, counts: [@nonce + 1, @nonce, @nonce])
    assert {:error, error} = Funding.settled(payment())
    assert error =~ "Base's block 4 has no transaction from the funder at nonce 7"
    assert count_blocks(node) == [4, 2, 3]
  end

  test "settling through the operator's action keeps a landed send counted" do
    attempt = Ash.Seed.seed!(Attempt, %{harness_id: "H10", wallet_id: "W03", state: :sending})

    landed =
      Ash.Seed.seed!(Payment, %{
        attempt_id: attempt.id,
        token: :usdc,
        state: :unknown,
        from: @funder,
        to: "0xagent",
        amount: 20_000,
        nonce: @nonce,
        raw: "0x",
        hash: @hash
      })

    base(
      receipts: [nil, receipt("0x1", 640)],
      latest: 1_000,
      passed: 640,
      blocks: %{640 => [transaction(@hash, @funder, @nonce)]}
    )

    assert {:ok, %{state: :confirmed, block: 640, settled_by: "sean"}} =
             WalletBench.settle_payment(landed, actor: %Operator{name: "sean"}, authorize?: false)
  end

  property "the search finds the block where the nonce passed, reading only pinned blocks it can reach" do
    check all(
            latest <- integer(1..50_000_000),
            back <- integer(0..(latest - 1)),
            nonce <- integer(0..3),
            max_runs: 200
          ) do
      passed = latest - back

      node =
        base(
          receipts: [nil, nil],
          latest: latest,
          passed: passed,
          nonce: nonce,
          blocks: %{passed => [transaction(@hash, @funder, nonce)]}
        )

      assert {:error, error} = Funding.settled(payment(nonce))
      assert error =~ "landed in Base's block #{passed},"

      blocks = count_blocks(node)
      assert Enum.all?(blocks, &(&1 in 1..latest))
      assert length(blocks) <= ceil(:math.log2(latest + 1)) + 1
    end
  end

  defp payment(nonce \\ @nonce), do: %Payment{from: @funder, nonce: nonce, hash: @hash}

  # A Base address: its finalized block number `latest`, pinned reads only up to `head`, the funder's nonce passing
  # `nonce` in block `passed` (never when nil) unless `counts` gives the answers in turn, and each receipt read
  # answered from `receipts` in turn.
  defp base(chain) do
    chain =
      Map.merge(%{nonce: @nonce, blocks: %{}, counts: nil}, Map.new(chain))

    head = Map.get(chain, :head, chain.latest)
    state = %{receipts: chain.receipts, counts: chain.counts, calls: []}
    {:ok, node} = Agent.start_link(fn -> state end)

    Req.Test.stub(__MODULE__, fn conn ->
      {:ok, body, conn} = Plug.Conn.read_body(conn)
      %{"method" => method, "params" => params} = Jason.decode!(body)
      Agent.update(node, &%{&1 | calls: &1.calls ++ [{method, params}]})
      Req.Test.json(conn, answer(method, params, chain, head, node))
    end)

    node
  end

  defp answer("eth_getTransactionReceipt", [@hash], _chain, _head, node),
    do: %{"result" => next(node, :receipts)}

  defp answer("eth_getBlockByNumber", ["finalized", false], chain, _head, _node),
    do: %{"result" => %{"number" => BaseRpc.hex(chain.latest)}}

  defp answer("eth_getTransactionCount", [@funder, tag], chain, head, node) do
    block = BaseRpc.integer(tag)

    cond do
      block > head -> %{"error" => %{"code" => -32_000, "message" => "header not found"}}
      chain.counts != nil -> %{"result" => BaseRpc.hex(next(node, :counts))}
      chain.passed != nil and block >= chain.passed -> %{"result" => BaseRpc.hex(chain.nonce + 1)}
      true -> %{"result" => BaseRpc.hex(chain.nonce)}
    end
  end

  defp answer("eth_getBlockByNumber", [tag, true], chain, _head, _node),
    do: %{"result" => %{"transactions" => Map.get(chain.blocks, BaseRpc.integer(tag), [])}}

  defp next(node, key),
    do:
      Agent.get_and_update(
        node,
        &{hd(Map.fetch!(&1, key)), Map.update!(&1, key, fn [_ | rest] -> rest end)}
      )

  defp receipt(status, block), do: %{"status" => status, "blockNumber" => BaseRpc.hex(block)}

  defp transaction(hash, from, nonce),
    do: %{"hash" => hash, "from" => from, "nonce" => BaseRpc.hex(nonce)}

  defp calls(node), do: Agent.get(node, & &1.calls)

  defp methods(node), do: Enum.map(calls(node), &elem(&1, 0))

  defp count_blocks(node) do
    for {"eth_getTransactionCount", [_from, "0x" <> _ = tag]} <- calls(node),
        do: BaseRpc.integer(tag)
  end
end
