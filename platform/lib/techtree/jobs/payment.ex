defmodule Techtree.Jobs.Payment do
  @moduledoc """
  How a job order is paid, with no chain read: the order's payment reference,
  the two calls whoever pays signs, and the rule that turns what was read from
  the chain into the order's next state.

  An order is paid by `depositUSDC(amount, tag, reference)` on REGENT revenue
  staking, after an approval of that amount on USDC. The tag is `source_tag`
  (`config :techtree, Techtree.Jobs`) in ASCII, right-padded with zero bytes to
  32, the way `RegentCredits` pads its own. Anyone may send the deposit: the
  wallet that sends it is recorded and never checked.
  """

  alias RegentChain.{Call, Review}

  @doc "The settings in `config :techtree, Techtree.Jobs`."
  @spec config() :: keyword()
  def config, do: Application.fetch_env!(:techtree, Techtree.Jobs)

  @doc "A new payment reference: 32 random bytes, as lowercase `0x` hex."
  @spec reference() :: String.t()
  def reference, do: hex(:crypto.strong_rand_bytes(32))

  @doc "The deposit's source tag, as the `bytes32` `depositUSDC` takes."
  @spec tag() :: String.t()
  def tag, do: hex(String.pad_trailing(config()[:source_tag], 32, <<0>>))

  @doc """
  The two calls that pay a quoted order, in order: the approval of exactly the
  quote on USDC, then the deposit. Each names its chain.
  """
  @spec calls(map()) :: {:ok, [map()]} | {:error, :not_quoted}
  def calls(%{state: :quoted, quote_amount: amount, payment_reference: reference}) do
    settings = config()

    {:ok,
     [
       call(
         settings,
         "approve",
         settings[:usdc],
         Call.encode("approve(address,uint256)", [settings[:staking], amount])
       ),
       call(
         settings,
         "deposit",
         settings[:staking],
         Call.encode("depositUSDC(uint256,bytes32,bytes32)", [amount, tag(), reference])
       )
     ]}
  end

  def calls(_order), do: {:error, :not_quoted}

  @doc """
  What a quoted order becomes once `received` has been saved: paid when it is
  at least the quote, otherwise expired once its quote has run out, otherwise
  still quoted. Paying wins: a deposit saved as the expiry is reached pays.
  """
  @spec outcome(pos_integer(), Decimal.t() | non_neg_integer(), boolean()) ::
          :paid | :expired | :quoted
  def outcome(quote_amount, received, expiry_passed?) do
    cond do
      Decimal.compare(received, quote_amount) != :lt -> :paid
      expiry_passed? -> :expired
      true -> :quoted
    end
  end

  defp call(settings, name, to, data),
    do: name |> Review.step(to, data) |> Map.put(:chain_id, settings[:chain_id])

  defp hex(bytes), do: "0x" <> Base.encode16(bytes, case: :lower)
end
