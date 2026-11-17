defmodule Techtree.JobsFixture do
  @moduledoc """
  Job orders for tests: agents and orders made through the domain's actions,
  and a stand-in Base node for the payment reader, so no test reaches a real
  one.

  `node/1` answers the JSON-RPC requests `Techtree.Jobs.Staking` makes from a
  plain map:

    * `:head`, the newest block's number, with `:time`, when it was made in
      Unix seconds (now unless given), and its hash `block_hash/1` unless
      `:head_hash` says otherwise;
    * `:logs`, every staking log on the chain (`log/1`), of which each
      `eth_getLogs` answers the ones logged by the contract asked for, of the
      topics asked for, in its blocks and at or below the head;
    * `:refuse_over`, the most blocks a log search may cover before the node
      refuses it, and `:refuse`, blocks the node refuses any search that
      covers;
    * `:chain_id` (8453), `:paused`, `:status`, an HTTP status every request
      gets, and `:down`, which makes every request fail as a node that cannot
      be reached does.

  Each log search sends `{:logs_asked, from, to}` to the process that put the
  node, so a test can see how the chain was asked, and first runs `:on_logs`,
  a function of no arguments, when the chain names one.
  """

  import ExUnit.Callbacks, only: [on_exit: 1]

  alias Techtree.{Agents, Jobs}
  alias Techtree.Actors.{Agent, System}
  alias Techtree.Jobs.Payment

  @topic0 "0x1a150e3db61cdcdf841d24acf00159c2e184f84c02c7ec5ab3507766dae59e51"
  @direct_deposit "0x" <> String.duplicate("0", 64)

  @doc "A signed agent with no person paired."
  def agent do
    {:ok, agent} = Agents.sign_in_agent(wallet(), actor: %System{})
    Agent.for_agent(agent)
  end

  @doc "An order `agent` asked for, in the skills lane."
  def order(agent) do
    Jobs.request_order!(:skills, "Refund routing", "The refund tests pass.", actor: agent)
  end

  @doc "An order checked and quoted by `admin`."
  def quoted(agent, admin, amount, expires_at \\ DateTime.add(DateTime.utc_now(), 7, :day)) do
    agent
    |> order()
    |> Jobs.check_order!(actor: admin)
    |> Jobs.quote_order!(amount, "The refund Skill, tested on the agreed tasks.", expires_at,
      actor: admin
    )
  end

  @doc "The reading job's arguments for the configured staking contract on Base."
  def reader, do: %{"chain_id" => 8453, "contract" => Payment.config()[:staking]}

  @doc "A fresh wallet address."
  def wallet, do: "0x" <> Base.encode16(:crypto.strong_rand_bytes(20), case: :lower)

  @doc "A fresh 32-byte value, as a reference or a transaction hash."
  def word, do: "0x" <> Base.encode16(:crypto.strong_rand_bytes(32), case: :lower)

  @doc "The stand-in chain's hash of block `number`."
  def block_hash(number), do: "0x" <> String.pad_leading(quantity_digits(number), 64, "0")

  @doc "Points the site's Base node at a stand-in answering from `chain` until the test ends."
  def node(chain) do
    test = self()

    put_env(:techtree, Techtree.ChainClient,
      req_options: [plug: {Req.Test, Techtree.ChainClient}]
    )

    Req.Test.stub(Techtree.ChainClient, fn conn ->
      cond do
        chain[:down] ->
          Req.Test.transport_error(conn, :econnrefused)

        chain[:status] ->
          Plug.Conn.send_resp(conn, chain.status, "")

        true ->
          {:ok, body, conn} = Plug.Conn.read_body(conn)
          %{"method" => method, "params" => params} = Jason.decode!(body)
          answer = answer(chain, method, params, test)
          Req.Test.json(conn, Map.merge(answer, %{"jsonrpc" => "2.0", "id" => 1}))
      end
    end)
  end

  defp answer(chain, "eth_chainId", [], _test),
    do: %{"result" => quantity(Map.get(chain, :chain_id, 8453))}

  defp answer(chain, "eth_getBlockByNumber", ["latest", false], _test) do
    %{
      "result" => %{
        "number" => quantity(chain.head),
        "hash" => Map.get(chain, :head_hash, block_hash(chain.head)),
        "timestamp" => quantity(Map.get_lazy(chain, :time, &now/0))
      }
    }
  end

  defp answer(chain, "eth_getLogs", [filter], test) do
    %{"address" => address, "fromBlock" => from, "toBlock" => to, "topics" => topics} = filter
    {from, to} = {block(from), block(to)}
    send(test, {:logs_asked, from, to})
    Map.get(chain, :on_logs, fn -> :ok end).()

    if refused?(chain, from, to) do
      %{"error" => %{"code" => -32_005, "message" => "query returned more than 10000 results"}}
    else
      %{
        "result" =>
          Enum.filter(Map.get(chain, :logs, []), fn log ->
            log["address"] == address and Enum.take(log["topics"], length(topics)) == topics and
              block(log["blockNumber"]) in from..min(to, chain.head)//1
          end)
      }
    end
  end

  defp answer(chain, "eth_call", [%{"data" => "0x5c975abb"}, "latest"], _test),
    do: %{"result" => "0x" <> String.pad_leading(if(chain[:paused], do: "1", else: "0"), 64, "0")}

  defp refused?(chain, from, to) do
    to - from + 1 > Map.get(chain, :refuse_over, to - from + 1) or
      Enum.any?(Map.get(chain, :refuse, []), &(&1 in from..to//1))
  end

  @doc """
  One `USDCRevenueDeposited` log as a node returns it: a direct deposit from
  `contract` (the staking contract unless given) carrying `reference`,
  received `amount`, by `depositor` (a fresh wallet unless given), in `block`,
  tagged `tag` (the jobs' own unless given), in a new transaction unless
  `transaction_hash` names one, at `log_index` (0), in a block whose hash is
  `block_hash/1` unless `block_hash` says otherwise.
  """
  def log(fields) do
    tag = Keyword.get(fields, :tag, Payment.tag())
    amount = Keyword.fetch!(fields, :amount)
    block = Keyword.fetch!(fields, :block)

    data =
      [amount, div(amount, 3), amount - div(amount, 3)]
      |> Enum.map(&String.pad_leading(Integer.to_string(&1, 16), 64, "0"))
      |> Enum.join()

    %{
      "address" => Keyword.get(fields, :contract, Payment.config()[:staking]),
      "topics" => [
        @topic0,
        @direct_deposit,
        "0x" <>
          String.duplicate("0", 24) <>
          String.trim_leading(Keyword.get_lazy(fields, :depositor, &wallet/0), "0x"),
        Keyword.fetch!(fields, :reference)
      ],
      "data" => "0x" <> String.downcase(data) <> String.trim_leading(tag, "0x"),
      "blockNumber" => quantity(block),
      "blockHash" => Keyword.get(fields, :block_hash, block_hash(block)),
      "transactionHash" => Keyword.get_lazy(fields, :transaction_hash, &word/0),
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

  @doc "Turns the payment reader on until the test ends."
  def read_payments,
    do: put_env(:techtree, Techtree.Jobs, Keyword.put(Payment.config(), :read_payments, true))

  defp now, do: DateTime.to_unix(DateTime.utc_now())
  defp quantity(number), do: "0x" <> quantity_digits(number)
  defp quantity_digits(number), do: String.downcase(Integer.to_string(number, 16))
  defp block("0x" <> hex), do: String.to_integer(hex, 16)
end
