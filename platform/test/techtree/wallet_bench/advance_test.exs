defmodule Techtree.WalletBench.AdvanceTest do
  # A funded money test that fails still hands the agent the turn that returns
  # what is left, because the machine's reset after the attempt erases its
  # wallet (attempt 09cda9c0, 21 Oct 2026, stranded 0.01 USDC that way). Once
  # the return ends, the attempt stops with the money test's own failure.
  use Techtree.DataCase, async: false
  use Oban.Testing, repo: Techtree.Repo

  alias Techtree.WalletBench.{Attempt, Machine, Payment, Turn}

  @funder "0x786C67651BcB148f5A383A150E78bD4Ed9f64f7b"
  @agent "0x260449A6ad0c93F8ceA18BAf9A269aB1ec3256aF"
  @started ~U[2026-10-21 09:37:47.000000Z]

  test "a failed money test queues the return in the latest conversation; the attempt stops with its reason" do
    attempt = funded_attempt!()
    t3 = turn!(attempt, :T3, :finished, nil, 120)

    fail!(t3, "Base RPC eth_getLogs answered 429 with error -32011")

    assert %Attempt{state: :testing} = attempt = reload(attempt)

    assert [%Turn{state: :queued, resume_session_id: "codex-session-1"} = return] =
             Enum.filter(attempt.turns, &(&1.test == :return))

    assert return.prompt =~ @funder

    fail!(return, "The machine did not answer.")

    assert %Attempt{state: :revoking, failure: failure} = reload(attempt)

    assert failure =~ "T3"
    assert failure =~ "eth_getLogs answered 429"
  end

  test "a failed return stops the attempt with its own reason" do
    attempt = funded_attempt!()
    turn!(attempt, :T5, :judged, "codex-session-1", 300)
    return = turn!(attempt, :return, :running, nil, 360)

    fail!(return, "The machine did not answer.")

    assert %Attempt{state: :revoking, failure: failure} = reload(attempt)

    assert failure =~ "The machine did not answer."
    assert [%Turn{state: :failed}] = Enum.filter(reload(attempt).turns, &(&1.test == :return))
  end

  defp reload(attempt), do: Ash.get!(Attempt, attempt.id, load: [:turns], authorize?: false)

  defp fail!(turn, error) do
    turn
    |> Ash.Changeset.for_update(:mark_failed, %{error: error})
    |> Ash.update!(authorize?: false)
  end

  defp funded_attempt! do
    batch = Ecto.UUID.generate()

    machine =
      Ash.Seed.seed!(Machine, %{
        batch_id: batch,
        name: "wb-test-advance-#{String.slice(batch, 0, 8)}",
        state: :leased,
        harness_id: "H10"
      })

    attempt =
      Ash.Seed.seed!(Attempt, %{
        batch_id: batch,
        replicate: 1,
        harness_id: "H10",
        wallet_id: "W03",
        state: :testing,
        plan: :money,
        agent_address: @agent,
        machine_id: machine.id
      })

    Ash.Seed.seed!(Payment, %{
      attempt_id: attempt.id,
      token: :usdc,
      state: :confirmed,
      from: @funder,
      to: @agent,
      amount: 20_000,
      nonce: 0,
      raw: "0x02",
      hash: "0x" <> String.duplicate("a", 64),
      block: 52_893_212
    })

    turn!(attempt, :T2, :judged, "codex-session-1", 60)
    attempt
  end

  defp turn!(attempt, test, state, session_id, offset) do
    Ash.Seed.seed!(Turn, %{
      attempt_id: attempt.id,
      test: test,
      state: state,
      prompt: "A money test.",
      session_id: session_id,
      inserted_at: DateTime.add(@started, offset)
    })
  end
end
