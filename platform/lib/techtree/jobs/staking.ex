defmodule Techtree.Jobs.Staking do
  @moduledoc """
  The reads of Base that job orders need, through the site's own Base node
  (`Techtree.ChainClient`): the newest block, a block's time, the deposits that
  carry one order's payment reference, and whether REGENT revenue staking is
  paused.

  A deposit is a `USDCRevenueDeposited` log from the staking contract: a direct
  deposit (`sourceKind` 0) by `depositor` with `sourceRef` the reference, and in
  its data the amount received and the source tag. Only deposits tagged with
  the jobs' `source_tag` are kept; one with any other tag is not a job payment.
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

  @type deposit :: %{
          transaction_hash: String.t(),
          log_index: non_neg_integer(),
          depositor: String.t(),
          amount: non_neg_integer(),
          block_number: non_neg_integer()
        }

  @doc "The newest block's number."
  @spec head() :: {:ok, non_neg_integer()} | {:error, term()}
  def head do
    with {:ok, number} <- rpc("eth_blockNumber", []), do: quantity(number)
  end

  @doc "The time of block `number`, in Unix seconds."
  @spec block_time(non_neg_integer()) :: {:ok, non_neg_integer()} | {:error, term()}
  def block_time(number) do
    case rpc("eth_getBlockByNumber", [quantity_hex(number), false]) do
      {:ok, %{"timestamp" => timestamp}} -> quantity(timestamp)
      {:ok, block} -> {:error, {:malformed_block, block}}
      error -> error
    end
  end

  @doc """
  The job payments carrying `reference` in blocks `from` to `to`. A log that is
  not the deposit it was asked for is an error, never skipped.
  """
  @spec deposits(String.t(), non_neg_integer(), non_neg_integer()) ::
          {:ok, [deposit()]} | {:error, term()}
  def deposits(reference, from, to) do
    filter = %{
      address: Payment.config()[:staking],
      fromBlock: quantity_hex(from),
      toBlock: quantity_hex(to),
      topics: [@topic0, @direct_deposit, nil, reference]
    }

    case rpc("eth_getLogs", [filter]) do
      {:ok, logs} when is_list(logs) -> decode_all(logs, reference, [])
      {:ok, other} -> {:error, {:malformed_logs, other}}
      error -> error
    end
  end

  defp decode_all([], _reference, deposits), do: {:ok, Enum.reverse(deposits)}

  defp decode_all([log | logs], reference, deposits) do
    case decode(log, reference) do
      {:ok, nil} -> decode_all(logs, reference, deposits)
      {:ok, deposit} -> decode_all(logs, reference, [deposit | deposits])
      :error -> {:error, {:malformed_log, log}}
    end
  end

  @doc """
  One log as a job payment carrying `reference`: `{:ok, deposit}`, `{:ok, nil}`
  for a deposit with another tag, and `:error` for anything that is not a direct
  deposit by the staking contract with that reference.
  """
  @spec decode(map(), String.t()) :: {:ok, deposit() | nil} | :error
  def decode(
        %{
          "address" => address,
          "topics" => [@topic0, @direct_deposit, depositor_topic, reference_topic],
          "data" => data,
          "blockNumber" => block_number,
          "transactionHash" => transaction_hash,
          "logIndex" => log_index
        },
        reference
      ) do
    with true <- String.downcase(address) == Payment.config()[:staking],
         true <- String.downcase(reference_topic) == reference,
         {:ok, depositor_word} <- Abi.bytes(depositor_topic),
         {:ok, depositor} <- Abi.word(depositor_word, :address),
         {:ok, data} <- Abi.bytes(data),
         {:ok, [amount, _credited, _residual, tag]} <- Abi.decode(data, @data),
         {:ok, block_number} <- Abi.quantity(block_number),
         {:ok, transaction_hash} <- Abi.hash(transaction_hash),
         {:ok, log_index} <- Abi.quantity(log_index) do
      if tag == Payment.tag() do
        {:ok,
         %{
           transaction_hash: transaction_hash,
           log_index: log_index,
           depositor: depositor,
           amount: amount,
           block_number: block_number
         }}
      else
        {:ok, nil}
      end
    else
      _other -> :error
    end
  end

  def decode(_log, _reference), do: :error

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

  defp rpc(method, params),
    do: ChainClient.rpc(%{chain_id: Payment.config()[:chain_id]}, method, params, @scope)

  defp quantity(value) do
    case Abi.quantity(value) do
      {:ok, number} -> {:ok, number}
      :error -> {:error, {:malformed_quantity, value}}
    end
  end

  defp quantity_hex(number), do: "0x" <> String.downcase(Integer.to_string(number, 16))
end
