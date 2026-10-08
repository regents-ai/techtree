defmodule Techtree.WalletBench.Funding do
  @moduledoc """
  Funding a money attempt from the bench's funder wallet: 0.25 USDC and
  0.00003 ETH for gas (the amounts in `:techtree, Techtree.WalletBench,
  funding`), as two sends on Base.

  `prepare/1` decides and signs; nothing is broadcast there. It refuses, with
  the reason, when funding is paused, when the run's totals would pass their
  caps, when the agent's address is the funder's or already holds anything or
  has sent anything, or when the funder cannot pay. Funding is paused while any
  send is `unknown`, or while a money test's safety failure has not been
  cleared by an operator. Each send takes the next funder nonce, after both the
  chain's pending count and every nonce the bench already signed.

  `receipts/1` broadcasts the signed bytes again, which is harmless for a
  transaction already sent, and reads each receipt.
  """

  require Ash.Query

  import Techtree.WalletBench.BaseRpc, only: [call: 2, integer: 1]

  alias Techtree.WalletBench.{BaseCheck, BaseRpc, Funder, Payment, Turn}

  @chain_id 8453
  @usdc_gas 100_000
  @eth_gas 21_000

  @type send :: %{
          token: :usdc | :eth,
          from: String.t(),
          to: String.t(),
          amount: pos_integer(),
          nonce: non_neg_integer(),
          raw: String.t(),
          hash: String.t()
        }

  @doc "The two signed sends for an attempt's agent address, or why it is not funded."
  @spec prepare(String.t()) :: {:ok, [send()]} | {:refuse, String.t()} | {:error, term()}
  def prepare(address) do
    caps = caps()

    with :ok <- not_paused(),
         :ok <- within_totals(caps),
         {:ok, funder} <- Funder.address(),
         :ok <- not_funder(address, funder),
         {:ok, chain_id} <- call("eth_chainId", []),
         :ok <- on_base(integer(chain_id)),
         {:ok, agent} <- BaseCheck.check(address, nil),
         :ok <- untouched(agent),
         {:ok, fees} <- fees(),
         :ok <- funder_can_pay(funder, caps, fees),
         {:ok, nonce} <- next_nonce(funder) do
      sign(funder, String.downcase(address), caps, fees, nonce)
    end
  end

  @doc """
  Each send's receipt on Base after broadcasting it again: `{:confirmed, block}`,
  `{:reverted, block}` or `:pending`.
  """
  @spec receipts([struct()]) :: {:ok, [{struct(), term()}]} | {:error, term()}
  def receipts(payments) do
    Enum.reduce_while(payments, {:ok, []}, fn payment, {:ok, done} ->
      # A send already on the chain, or already known to it, is refused again; the receipt decides.
      _broadcast = call("eth_sendRawTransaction", [payment.raw])

      case call("eth_getTransactionReceipt", [payment.hash]) do
        {:ok, nil} -> {:cont, {:ok, done ++ [{payment, :pending}]}}
        {:ok, receipt} -> {:cont, {:ok, done ++ [{payment, outcome(receipt)}]}}
        {:error, error} -> {:halt, {:error, error}}
      end
    end)
  end

  defp outcome(%{"status" => "0x1", "blockNumber" => block}), do: {:confirmed, integer(block)}
  defp outcome(%{"blockNumber" => block}), do: {:reverted, integer(block)}

  defp caps, do: Application.fetch_env!(:techtree, Techtree.WalletBench)[:funding]

  defp not_paused do
    unknown = Payment |> Ash.Query.filter(state == :unknown) |> Ash.read!()

    safety =
      Turn
      |> Ash.Query.filter(
        test in [:T3, :T4, :T5] and fragment("(? ->> 'outcome') = 'FAILED_SAFETY'", judgment) and
          is_nil(attempt.safety_cleared)
      )
      |> Ash.read!()

    cond do
      unknown != [] ->
        {:refuse,
         "Funding is paused: the outcome of the send #{hd(unknown).hash} is not known yet."}

      safety != [] ->
        {:refuse,
         "Funding is paused: a money test ended in a safety failure, on the attempt #{hd(safety).attempt_id}."}

      true ->
        :ok
    end
  end

  # Every send counts except one that never reached the chain.
  defp within_totals(caps) do
    sent =
      Payment
      |> Ash.Query.filter(state not in [:reverted, :dropped])
      |> Ash.read!()
      |> Enum.group_by(& &1.token, & &1.amount)
      |> Map.new(fn {token, amounts} -> {token, Enum.sum(amounts)} end)

    usdc = Map.get(sent, :usdc, 0) + caps[:usdc_units]
    eth = Map.get(sent, :eth, 0) + caps[:eth_wei]

    if usdc <= caps[:total_usdc_units] and eth <= caps[:total_eth_wei],
      do: :ok,
      else: {:refuse, "Funding this attempt would pass the run's total for the funder."}
  end

  defp not_funder(address, funder) do
    if String.downcase(address) == funder,
      do: {:refuse, "The agent's address is the funder's own."},
      else: :ok
  end

  defp on_base(@chain_id), do: :ok
  defp on_base(chain_id), do: {:error, "The bench's Base RPC answers for chain #{chain_id}."}

  defp untouched(%{"problem" => problem}), do: {:refuse, problem}

  defp untouched(%{"eth_wei" => 0, "usdc_units" => 0, "nonce" => nonce, "code_bytes" => code})
       when nonce == 0 or code > 0,
       do: :ok

  defp untouched(check) do
    {:refuse,
     "The agent's address was not new on Base at block #{check["block"]}: it held " <>
       "#{check["eth_wei"]} wei and #{check["usdc_units"]} USDC units, with nonce #{check["nonce"]}."}
  end

  # The fee cap allows the base fee to double before the sends are included.
  defp fees do
    with {:ok, block} <- call("eth_getBlockByNumber", ["latest", false]),
         {:ok, tip} <- call("eth_maxPriorityFeePerGas", []) do
      tip = integer(tip)
      {:ok, %{tip: tip, max: 2 * integer(block["baseFeePerGas"]) + tip}}
    end
  end

  defp funder_can_pay(funder, caps, fees) do
    gas = (@usdc_gas + @eth_gas) * fees.max

    with {:ok, wei} <- call("eth_getBalance", [funder, "latest"]),
         {:ok, usdc} <- BaseRpc.usdc_balance(funder, "latest") do
      if usdc >= caps[:usdc_units] and integer(wei) >= caps[:eth_wei] + gas,
        do: :ok,
        else:
          {:refuse,
           "The funder holds #{usdc} USDC units and #{integer(wei)} wei, too little for this attempt."}
    end
  end

  defp next_nonce(funder) do
    signed =
      Payment
      |> Ash.Query.filter(from == ^funder)
      |> Ash.Query.sort(nonce: :desc)
      |> Ash.Query.limit(1)
      |> Ash.read!()

    with {:ok, pending} <- call("eth_getTransactionCount", [funder, "pending"]) do
      case signed do
        [last] -> {:ok, max(integer(pending), last.nonce + 1)}
        [] -> {:ok, integer(pending)}
      end
    end
  end

  defp sign(funder, address, caps, fees, nonce) do
    sends = [
      %{
        token: :usdc,
        amount: caps[:usdc_units],
        fields: %{
          to: BaseRpc.usdc(),
          value: 0,
          data: BaseRpc.usdc_transfer(address, caps[:usdc_units]),
          gas: @usdc_gas
        }
      },
      %{
        token: :eth,
        amount: caps[:eth_wei],
        fields: %{to: address, value: caps[:eth_wei], data: "0x", gas: @eth_gas}
      }
    ]

    sends
    |> Enum.with_index(nonce)
    |> Enum.reduce_while({:ok, []}, fn {send, nonce}, {:ok, done} ->
      fields =
        Map.merge(send.fields, %{
          chain_id: @chain_id,
          nonce: nonce,
          max_priority_fee_per_gas: fees.tip,
          max_fee_per_gas: fees.max
        })

      case Funder.sign(fields) do
        {:ok, signed} ->
          {:cont,
           {:ok,
            done ++
              [
                %{
                  token: send.token,
                  from: funder,
                  to: address,
                  amount: send.amount,
                  nonce: nonce,
                  raw: signed.raw,
                  hash: signed.hash
                }
              ]}}

        {:error, error} ->
          {:halt, {:error, error}}
      end
    end)
  end
end
