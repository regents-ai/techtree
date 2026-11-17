defmodule Techtree.Jobs.Staking do
  @moduledoc """
  The reads of Base that job payments need, through the site's own Base node
  (`Techtree.ChainClient`), always at the latest block: the chain the node
  serves, the newest block, REGENT revenue staking's direct deposits in a
  stretch of blocks, and whether staking is paused.

  A job payment is a `USDCRevenueDeposited` log from the staking contract: a
  direct deposit (`sourceKind` 0) by `depositor` with `sourceRef` an order's
  payment reference, and in its data the amount received and the source tag.
  Logs are asked for by the event and the direct-deposit kind; of those, only
  the ones tagged with the jobs' `source_tag` are job payments.

  A node that does not answer (no connection, a timeout, a 429 or a 5xx) is
  `{:error, :unavailable}`, and a request it answers with an error is
  `{:error, {:refused, error}}`.
  """

  alias RegentChain.{Abi, Event}
  alias Techtree.ChainClient
  alias Techtree.Jobs.Payment

  @topic0 Event.topic0(
            "USDCRevenueDeposited(uint256,uint256,uint256,uint8,address,bytes32,bytes32)"
          )
  @direct_deposit "0x" <> String.duplicate("0", 64)
  @data [{:uint, 256}, {:uint, 256}, {:uint, 256}, :bytes32]
  @scope "jobs"

  @type head :: %{number: non_neg_integer(), hash: String.t(), timestamp: DateTime.t()}

  @type deposit :: %{
          contract: String.t(),
          transaction_hash: String.t(),
          log_index: non_neg_integer(),
          block_number: non_neg_integer(),
          block_hash: String.t(),
          depositor: String.t(),
          reference: String.t(),
          amount: Decimal.t()
        }

  @doc "The chain the node serves."
  @spec chain_id() :: {:ok, pos_integer()} | {:error, term()}
  def chain_id do
    with {:ok, id} <- rpc("eth_chainId", []), do: quantity(id)
  end

  @doc "The newest block: its number, its hash and when it was made."
  @spec head() :: {:ok, head()} | {:error, term()}
  def head do
    case rpc("eth_getBlockByNumber", ["latest", false]) do
      {:ok, %{"number" => number, "hash" => hash, "timestamp" => timestamp} = block} ->
        with {:ok, number} <- Abi.quantity(number),
             {:ok, hash} <- Abi.hash(hash),
             {:ok, timestamp} <- Abi.quantity(timestamp) do
          {:ok, %{number: number, hash: hash, timestamp: DateTime.from_unix!(timestamp)}}
        else
          :error -> {:error, {:malformed_block, block}}
        end

      {:ok, block} ->
        {:error, {:malformed_block, block}}

      error ->
        error
    end
  end

  @doc "Every direct deposit `contract` logged in blocks `from` to `to`, as the node gave them."
  @spec logs(String.t(), non_neg_integer(), non_neg_integer()) ::
          {:ok, [map()]} | {:error, term()}
  def logs(contract, from, to) do
    filter = %{
      address: contract,
      fromBlock: quantity_hex(from),
      toBlock: quantity_hex(to),
      topics: [@topic0, @direct_deposit]
    }

    case rpc("eth_getLogs", [filter]) do
      {:ok, logs} when is_list(logs) -> {:ok, logs}
      {:ok, other} -> {:error, {:malformed_logs, other}}
      error -> error
    end
  end

  @doc """
  One log as a job payment to `contract`: `{:ok, deposit}`, `{:ok, nil}` for a
  deposit with another tag, which is not a job payment, and `:error` for
  anything that is not a direct deposit logged by `contract`.
  """
  @spec decode(map(), String.t()) :: {:ok, deposit() | nil} | :error
  def decode(
        %{
          "address" => address,
          "topics" => [@topic0, @direct_deposit, depositor_topic, reference_topic],
          "data" => data,
          "blockNumber" => block_number,
          "blockHash" => block_hash,
          "transactionHash" => transaction_hash,
          "logIndex" => log_index
        },
        contract
      ) do
    with true <- String.downcase(address) == contract,
         {:ok, depositor_word} <- Abi.bytes(depositor_topic),
         {:ok, depositor} <- Abi.word(depositor_word, :address),
         {:ok, reference} <- Abi.hash(reference_topic),
         {:ok, data} <- Abi.bytes(data),
         {:ok, [amount, _credited, _residual, tag]} <- Abi.decode(data, @data),
         {:ok, block_number} <- Abi.quantity(block_number),
         {:ok, block_hash} <- Abi.hash(block_hash),
         {:ok, transaction_hash} <- Abi.hash(transaction_hash),
         {:ok, log_index} <- Abi.quantity(log_index) do
      {:ok,
       if tag == Payment.tag() do
         %{
           contract: contract,
           transaction_hash: transaction_hash,
           log_index: log_index,
           block_number: block_number,
           block_hash: block_hash,
           depositor: depositor,
           reference: reference,
           amount: Decimal.new(amount)
         }
       end}
    else
      _other -> :error
    end
  end

  def decode(_log, _contract), do: :error

  @doc "Whether REGENT revenue staking is paused at the newest block, so a deposit would fail."
  @spec paused() :: {:ok, boolean()} | {:error, term()}
  def paused do
    with {:ok, result} <-
           rpc("eth_call", [%{to: Payment.config()[:staking], data: "0x5c975abb"}, "latest"]),
         {:ok, bytes} <- Abi.bytes(result),
         {:ok, [paused]} <- Abi.decode(bytes, [:bool]) do
      {:ok, paused}
    else
      {:error, reason} -> {:error, reason}
      _malformed -> {:error, :malformed_result}
    end
  end

  defp rpc(method, params) do
    case ChainClient.rpc(%{chain_id: Payment.config()[:chain_id]}, method, params, @scope) do
      {:ok, result} -> {:ok, result}
      {:error, {:rpc, error}} -> {:error, {:refused, error}}
      {:error, {:http, status}} when status == 429 or status >= 500 -> {:error, :unavailable}
      {:error, %Req.TransportError{}} -> {:error, :unavailable}
      {:error, reason} -> {:error, reason}
    end
  end

  defp quantity(value) do
    case Abi.quantity(value) do
      {:ok, number} -> {:ok, number}
      :error -> {:error, {:malformed_quantity, value}}
    end
  end

  defp quantity_hex(number), do: "0x" <> String.downcase(Integer.to_string(number, 16))
end
