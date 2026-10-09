defmodule Techtree.WalletBench.Funding do
  @moduledoc """
  Funding a money attempt from the bench's funder wallet: 0.25 USDC and
  0.00003 ETH for gas (the amounts in `:techtree, Techtree.WalletBench,
  funding`), as two sends on Base.

  `prepare/1` decides and signs; nothing is broadcast there. It refuses, with
  the reason, when funding is paused, when the run's totals would pass their
  caps, when the agent's address is the funder's or already holds anything or
  has sent anything, when Base answers that either send would fail, or when
  the funder cannot pay. Funding is paused while any send is `unknown`, or
  while a money test's safety failure has not been cleared by an operator.
  Each send takes the next funder nonce, after both the chain's pending count
  and every nonce the bench already signed, and the gas Base estimates for it.
  `admit/1` checks the totals again where the sends are kept, so two
  preparations at once can never both spend the last of a total.

  `receipts/1` broadcasts the signed bytes again, which is harmless for a
  transaction already sent, and reads each receipt. `settled/1` only reads.

  Base's gas price is capped by `max_fee_per_gas_wei` in the funding settings,
  and each send's gas by `max_gas_per_send`: above either, nothing is signed.
  """

  require Ash.Query

  import Techtree.WalletBench.BaseRpc, only: [call: 2, integer: 1]

  alias Techtree.WalletBench.{BaseCheck, BaseRpc, Funder, Payment, Turn}

  @chain_id 8453

  # The lock `admit/1` holds while sends are kept: one number for the whole funder, on every app instance.
  @funding_lock :erlang.phash2(__MODULE__)

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
    address = String.downcase(address)

    with :ok <- not_paused(),
         :ok <- within_totals(%{usdc: caps[:usdc_units], eth: caps[:eth_wei]}),
         {:ok, funder} <- Funder.address(),
         :ok <- not_funder(address, funder),
         {:ok, chain_id} <- call("eth_chainId", []),
         :ok <- on_base(integer(chain_id)),
         {:ok, agent} <- BaseCheck.check(address, nil),
         :ok <- untouched(agent),
         {:ok, fees} <- fees(caps),
         {:ok, sends} <- gas_limits(sends(address, caps), funder, caps),
         :ok <- funder_can_pay(funder, sends, fees),
         {:ok, nonce} <- next_nonce(funder) do
      sign(funder, address, sends, fees, nonce)
    end
  end

  @doc """
  Inside the database transaction that keeps an attempt's signed `sends`:
  waits until no other funding is being kept, on any app instance (a Postgres
  lock held until this transaction ends), then refuses the sends when they and
  every send kept so far would pass the run's totals. A preparation that was
  within the totals when it was signed, but no longer is, is refused here,
  before anything is broadcast.
  """
  @spec admit([send()]) :: :ok | {:refuse, String.t()}
  def admit(sends) do
    Techtree.Repo.query!("SELECT pg_advisory_xact_lock($1)", [@funding_lock])
    within_totals(%{usdc: amount(sends, :usdc), eth: amount(sends, :eth)})
  end

  @doc """
  What became of an unknown send, read from Base without sending anything:
  `{:confirmed, block}` or `{:reverted, block}` from its receipt, or
  `:replaced` when there is no receipt and the funder's nonce at the latest
  block has passed it. The nonce is read first, so a send included between the
  two reads is seen by its receipt, never taken as replaced.
  """
  @spec settled(struct()) ::
          {:ok, {:confirmed | :reverted, non_neg_integer()} | :replaced} | {:error, String.t()}
  def settled(payment) do
    with {:ok, nonce} <- call("eth_getTransactionCount", [payment.from, "latest"]),
         {:ok, receipt} <- call("eth_getTransactionReceipt", [payment.hash]) do
      cond do
        receipt != nil ->
          {:ok, outcome(receipt)}

        integer(nonce) > payment.nonce ->
          {:ok, :replaced}

        true ->
          {:error,
           "Base has no receipt for #{payment.hash}, and the funder's nonce #{payment.nonce} is still unused, " <>
             "so the send can still land. It stays unknown until that nonce is used on Base."}
      end
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

  # Every send counts except one that moved nothing: reverted, or replaced at its nonce.
  defp within_totals(adding) do
    caps = caps()
    sent = Payment |> Ash.Query.filter(state not in [:reverted, :replaced]) |> Ash.read!()

    if amount(sent, :usdc) + adding.usdc <= caps[:total_usdc_units] and
         amount(sent, :eth) + adding.eth <= caps[:total_eth_wei],
       do: :ok,
       else: {:refuse, "Funding this attempt would pass the run's total for the funder."}
  end

  defp amount(sends, token),
    do: sends |> Enum.filter(&(&1.token == token)) |> Enum.map(& &1.amount) |> Enum.sum()

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
  defp fees(caps) do
    with {:ok, block} <- call("eth_getBlockByNumber", ["latest", false]),
         {:ok, tip} <- call("eth_maxPriorityFeePerGas", []) do
      tip = integer(tip)
      max = 2 * integer(block["baseFeePerGas"]) + tip

      if max <= caps[:max_fee_per_gas_wei],
        do: {:ok, %{tip: tip, max: max}},
        else:
          {:refuse,
           "Base's gas price needs a fee cap of #{max} wei per gas, over the bench's ceiling of #{caps[:max_fee_per_gas_wei]}."}
    end
  end

  defp sends(address, caps) do
    [
      %{
        token: :usdc,
        amount: caps[:usdc_units],
        fields: %{
          to: BaseRpc.usdc(),
          value: 0,
          data: BaseRpc.usdc_transfer(address, caps[:usdc_units])
        }
      },
      %{
        token: :eth,
        amount: caps[:eth_wei],
        fields: %{to: address, value: caps[:eth_wei], data: "0x"}
      }
    ]
  end

  # Each send's gas is Base's own estimate for it, from the funder, with a fifth more for headroom: an address whose
  # code needs gas to take ETH gets it, and one that refuses the ETH is refused before the USDC is sent.
  defp gas_limits(sends, funder, caps) do
    Enum.reduce_while(sends, {:ok, []}, fn send, {:ok, done} ->
      transaction = Map.merge(send.fields, %{from: funder, value: BaseRpc.hex(send.fields.value)})

      case BaseRpc.estimate_gas(transaction) do
        {:ok, estimate} ->
          limited(send, done, div(estimate * 6, 5), caps[:max_gas_per_send])

        {:refused, reason} ->
          {:halt, {:refuse, refused(send.token, reason)}}

        {:error, error} ->
          {:halt, {:error, error}}
      end
    end)
  end

  defp limited(send, done, gas, ceiling) when gas <= ceiling,
    do: {:cont, {:ok, done ++ [put_in(send, [:fields, :gas], gas)]}}

  defp limited(send, _done, gas, ceiling) do
    {:halt,
     {:refuse,
      "The #{send.token} send needs #{gas} gas, over the bench's ceiling of #{ceiling} per send."}}
  end

  defp refused(:usdc, reason),
    do: "Base answers that the USDC send to the agent's address would fail: #{reason}"

  defp refused(:eth, reason),
    do: "Base answers that the agent's address would not take the ETH for gas: #{reason}"

  defp funder_can_pay(funder, sends, fees) do
    gas = sends |> Enum.map(& &1.fields.gas) |> Enum.sum() |> Kernel.*(fees.max)

    with {:ok, wei} <- call("eth_getBalance", [funder, "latest"]),
         {:ok, usdc} <- BaseRpc.usdc_balance(funder, "latest") do
      if usdc >= amount(sends, :usdc) and integer(wei) >= amount(sends, :eth) + gas,
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

  defp sign(funder, address, sends, fees, nonce) do
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
