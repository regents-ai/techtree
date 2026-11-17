defmodule Techtree.JobsFixture do
  @moduledoc """
  Job orders for tests: agents and orders made through the domain's actions,
  and a stand-in Base node for the payment reads, so no test reaches a real one.

  `node/1` answers the JSON-RPC requests `Techtree.Jobs.Staking` makes from a
  plain map: `:head`, the newest block; `:logs`, every deposit log on the chain
  (`log/1`), of which each `eth_getLogs` answers the ones in its blocks with
  its reference; `:time`, a block's time from its number; `:paused`; and
  `:down`, which makes every request fail as a node that cannot be reached does.
  """

  import ExUnit.Callbacks, only: [on_exit: 1]

  alias Techtree.{Agents, Jobs}
  alias Techtree.Actors.{Agent, System}
  alias Techtree.Jobs.Payment

  @topic0 "0x1a150e3db61cdcdf841d24acf00159c2e184f84c02c7ec5ab3507766dae59e51"

  @doc "A signed agent with no person paired."
  def agent do
    wallet = "0x" <> Base.encode16(:crypto.strong_rand_bytes(20), case: :lower)
    {:ok, agent} = Agents.sign_in_agent(wallet, actor: %System{})
    Agent.for_agent(agent)
  end

  @doc "An order `agent` asked for, in the skills lane."
  def order(agent) do
    Jobs.request_order!(:skills, "Refund routing", "The refund tests pass.", actor: agent)
  end

  @doc "An order checked and quoted by `admin`, with the node's head where `node/1` put it."
  def quoted(agent, admin, amount, expires_at \\ DateTime.add(DateTime.utc_now(), 7, :day)) do
    agent
    |> order()
    |> Jobs.check_order!(actor: admin)
    |> Jobs.quote_order!(amount, "The refund Skill, tested on the agreed tasks.", expires_at,
      actor: admin
    )
  end

  @doc "Points the site's Base node at a stand-in answering from `chain` until the test ends."
  def node(chain) do
    put_env(:techtree, Techtree.ChainClient,
      req_options: [plug: {Req.Test, Techtree.ChainClient}]
    )

    Req.Test.stub(Techtree.ChainClient, fn conn ->
      if chain[:down] do
        Req.Test.transport_error(conn, :econnrefused)
      else
        {:ok, body, conn} = Plug.Conn.read_body(conn)
        %{"method" => method, "params" => params} = Jason.decode!(body)

        Req.Test.json(conn, %{
          "jsonrpc" => "2.0",
          "id" => 1,
          "result" => answer(chain, method, params)
        })
      end
    end)
  end

  defp answer(chain, "eth_blockNumber", []), do: quantity(chain.head)

  defp answer(chain, "eth_getBlockByNumber", [number, false]),
    do: %{"timestamp" => quantity(Map.get(chain, :time, &(&1 * 2)).(block(number)))}

  defp answer(chain, "eth_getLogs", [%{"fromBlock" => from, "toBlock" => to, "topics" => topics}]) do
    [@topic0, _direct, nil, reference] = topics

    Enum.filter(Map.get(chain, :logs, []), fn log ->
      List.last(log["topics"]) == reference and
        block(log["blockNumber"]) in block(from)..block(to)//1
    end)
  end

  defp answer(chain, "eth_call", [%{"data" => "0x5c975abb"}, "latest"]),
    do: "0x" <> String.pad_leading(if(chain[:paused], do: "1", else: "0"), 64, "0")

  @doc """
  One `USDCRevenueDeposited` log as a node returns it: a direct deposit carrying
  `reference`, received `amount`, by `depositor`, in `block`, tagged `tag`
  (the jobs' own unless given).
  """
  def log(fields) do
    tag = Keyword.get(fields, :tag, Payment.tag())
    amount = Keyword.fetch!(fields, :amount)

    data =
      [amount, div(amount, 3), amount - div(amount, 3)]
      |> Enum.map(&String.pad_leading(Integer.to_string(&1, 16), 64, "0"))
      |> Enum.join()

    %{
      "address" => Payment.config()[:staking],
      "topics" => [
        @topic0,
        "0x" <> String.duplicate("0", 64),
        "0x" <> String.duplicate("0", 24) <> String.trim_leading(fields[:depositor], "0x"),
        Keyword.fetch!(fields, :reference)
      ],
      "data" => "0x" <> String.downcase(data) <> String.trim_leading(tag, "0x"),
      "blockNumber" => quantity(Keyword.fetch!(fields, :block)),
      "transactionHash" =>
        Keyword.get_lazy(fields, :transaction_hash, fn ->
          "0x" <> Base.encode16(:crypto.strong_rand_bytes(32), case: :lower)
        end),
      "logIndex" => quantity(Keyword.get(fields, :log_index, 0)),
      "removed" => false
    }
  end

  @doc "Puts `opts` in `app`'s `key` settings until the test ends."
  def put_env(app, key, opts) do
    old = Application.fetch_env(app, key)
    Application.put_env(app, key, opts)

    on_exit(fn ->
      case old do
        {:ok, value} -> Application.put_env(app, key, value)
        :error -> Application.delete_env(app, key)
      end
    end)
  end

  @doc "Makes the accounts named by `privy_user_ids` the site's admins until the test ends."
  def put_admins(privy_user_ids), do: put_env(:regent_agents, :admins, privy_user_ids)

  defp quantity(number), do: "0x" <> String.downcase(Integer.to_string(number, 16))
  defp block("0x" <> hex), do: String.to_integer(hex, 16)
end
