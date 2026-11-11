defmodule Techtree.WalletBench.FundingCapConcurrencyTest do
  # The code side of formal/wallet_bench_funding: attempts keeping their sends at once, each in its own
  # Postgres transaction, never keep more than the run's total. The transactions run on real connections
  # outside the test sandbox (one transaction holding everything would hide the race), so the rows are
  # committed and this test deletes them itself.
  use ExUnit.Case, async: false

  import Ecto.Query
  require Ash.Query

  alias Ecto.Adapters.SQL.Sandbox
  alias Techtree.Repo
  alias Techtree.WalletBench.{Attempt, Funding, Payment}

  @attempts 5

  setup do
    :ok = Sandbox.checkout(Repo, sandbox: false)

    settings = Application.fetch_env!(:techtree, Techtree.WalletBench)
    funding = settings[:funding]

    # Room for exactly two attempts' sends.
    Application.put_env(
      :techtree,
      Techtree.WalletBench,
      Keyword.put(
        settings,
        :funding,
        Keyword.merge(funding,
          total_usdc_units: 2 * funding[:usdc_units],
          total_eth_wei: 2 * funding[:eth_wei]
        )
      )
    )

    assert Repo.aggregate("wallet_bench_payments", :count) == 0

    attempts =
      for n <- 1..@attempts,
          do: Ash.Seed.seed!(Attempt, %{harness_id: "H10", wallet_id: "W0#{n}", state: :funding})

    on_exit(fn ->
      :ok = Sandbox.checkout(Repo, sandbox: false)
      ids = Enum.map(attempts, &Ecto.UUID.dump!(&1.id))
      Repo.delete_all(from p in "wallet_bench_payments", where: p.attempt_id in ^ids)
      Repo.delete_all(from a in "wallet_bench_attempts", where: a.id in ^ids)
      Application.put_env(:techtree, Techtree.WalletBench, settings)
    end)

    %{attempts: attempts, funding: funding}
  end

  test "attempts keeping their sends at once never pass the run's total", %{
    attempts: attempts,
    funding: funding
  } do
    test = self()

    tasks =
      attempts
      |> Enum.with_index()
      |> Enum.map(fn {attempt, n} ->
        Task.async(fn -> keep(test, attempt, sends(attempt, n, funding)) end)
      end)

    # Every transaction has made its first statement, its own update, before any of them takes the lock:
    # the order in which repeatable read would let every one of them through.
    for task <- tasks, do: assert_receive({:updated, pid} when pid == task.pid, 5_000)
    for task <- tasks, do: send(task.pid, :go)

    results = Task.await_many(tasks, 15_000)

    assert Enum.count(results, &(&1 == {:ok, :kept})) == 2
    assert Enum.count(results, &(&1 == {:error, :refused})) == @attempts - 2

    counted = Payment |> Ash.Query.filter(state not in [:reverted, :replaced]) |> Ash.read!()

    for {token, total} <- [usdc: 2 * funding[:usdc_units], eth: 2 * funding[:eth_wei]] do
      assert counted |> Enum.filter(&(&1.token == token)) |> Enum.map(& &1.amount) |> Enum.sum() <=
               total
    end
  end

  # What the attempt's funding step does in its transaction (Attempt.Changes.SignFunding): its own update,
  # then `Funding.admit/1`, then the signed payments only when admitted.
  defp keep(test, attempt, sends) do
    :ok = Sandbox.checkout(Repo, sandbox: false)

    Repo.transaction(fn ->
      Ash.Seed.update!(attempt, %{state: :sending})
      send(test, {:updated, self()})
      receive do: (:go -> :ok)

      case Funding.admit(sends) do
        :ok ->
          Enum.each(
            sends,
            &(Payment |> Ash.Changeset.for_create(:sign, &1) |> Ash.create!(authorize?: false))
          )

          :kept

        {:refuse, _reason} ->
          Repo.rollback(:refused)
      end
    end)
  end

  defp sends(attempt, n, funding) do
    for {token, amount, nonce} <- [
          {:usdc, funding[:usdc_units], 2 * n},
          {:eth, funding[:eth_wei], 2 * n + 1}
        ] do
      %{
        attempt_id: attempt.id,
        token: token,
        from: "0xfunder",
        to: "0xagent#{n}",
        amount: amount,
        nonce: nonce,
        raw: "0x",
        hash: "0x#{nonce}"
      }
    end
  end
end
