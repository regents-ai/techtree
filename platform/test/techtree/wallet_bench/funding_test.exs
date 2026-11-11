defmodule Techtree.WalletBench.FundingTest do
  # The funder's total (Sean, 8 October 2026: 10 USDC in all): of two attempts signed while one pair still fit, only
  # the first kept is admitted.
  use Techtree.DataCase, async: false

  alias Techtree.WalletBench.{Attempt, Funding, Payment}

  test "only one of two preparations fits the last of the run's total" do
    attempt = Ash.Seed.seed!(Attempt, %{harness_id: "H10", wallet_id: "W03", state: :sending})
    kept = Ash.Seed.seed!(Payment, send(attempt, :usdc, 9_980_000, 0))

    pair = fn nonce ->
      [send(attempt, :usdc, 20_000, nonce), send(attempt, :eth, 30_000_000_000_000, nonce + 1)]
    end

    assert Funding.admit(pair.(1)) == :ok
    Enum.each(pair.(1), &Ash.Seed.seed!(Payment, &1))

    assert {:refuse, "Funding this attempt would pass the run's total for the funder."} =
             Funding.admit(pair.(3))

    Ash.Seed.update!(kept, %{state: :reverted})
    assert Funding.admit(pair.(3)) == :ok
  end

  # Sentinel's age of the oldest unconfirmed funding send (TechtreeWeb.Telemetry).
  test "the oldest send still signed or unknown is the one waiting, and none waits once every send has ended" do
    attempt = Ash.Seed.seed!(Attempt, %{harness_id: "H10", wallet_id: "W03", state: :sending})
    now = DateTime.utc_now()

    seed = fn nonce, state, seconds_ago ->
      Ash.Seed.seed!(
        Payment,
        Map.merge(send(attempt, :usdc, 20_000, nonce), %{
          state: state,
          inserted_at: DateTime.add(now, -seconds_ago, :second)
        })
      )
    end

    assert Funding.unconfirmed_sends() == [{"wallet_bench_funding", nil}]

    for {state, nonce} <- Enum.with_index([:confirmed, :reverted, :replaced]) do
      seed.(nonce, state, 600)
    end

    assert Funding.unconfirmed_sends() == [{"wallet_bench_funding", nil}]

    signed = seed.(3, :signed, 60)
    unknown = seed.(4, :unknown, 300)

    assert [{"wallet_bench_funding", signed_at}] = Funding.unconfirmed_sends()
    assert DateTime.compare(signed_at, unknown.inserted_at) == :eq

    Ash.Seed.update!(unknown, %{state: :replaced})
    assert [{"wallet_bench_funding", signed_at}] = Funding.unconfirmed_sends()
    assert DateTime.compare(signed_at, signed.inserted_at) == :eq
  end

  defp send(attempt, token, amount, nonce) do
    %{
      attempt_id: attempt.id,
      token: token,
      state: :signed,
      from: "0xfunder",
      to: "0xagent#{nonce}",
      amount: amount,
      nonce: nonce,
      raw: "0x",
      hash: "0x#{nonce}"
    }
  end
end
