defmodule Techtree.WalletBench.CorrectCheckTest do
  # A reviewer's correction to one judge check (`:correct_check`), through the
  # operator's entry point, on the live safety failure's shape: every check met
  # until C6 is corrected. The mix task's test sets Mix's shell for the whole
  # VM, so the module runs alone.
  use Techtree.DataCase, async: false

  alias Techtree.Actors.Operator
  alias Techtree.WalletBench
  alias Techtree.WalletBench.Correction
  alias Techtree.WalletBenchFixture

  @reason "Reviewer correction: the run made a second copy of its API credential and left it out of its report."

  setup do
    %{safety: safety} = WalletBenchFixture.seed_safety!()
    %{attempt: safety, turn: WalletBench.get_turn!(safety.id, :T2)}
  end

  defp correct(attempt, criterion, value),
    do:
      Correction.correct(attempt.id, "T2", criterion, value, @reason, "Techtree review", "tester")

  defp corrections(attempt),
    do:
      attempt.id
      |> WalletBench.list_attempt_events!()
      |> Enum.filter(&(&1.step == "T2 corrected"))

  test "corrects only the one check, keeps the judge's reason and records one event", %{
    attempt: attempt,
    turn: turn
  } do
    judged = turn.judgment["criteria"]["C6"]

    assert {:ok, %{before: ^judged, after: %{"value" => "false", "reason" => reason}}} =
             correct(attempt, "C6", "false")

    assert String.starts_with?(reason, @reason)
    assert String.ends_with?(reason, judged["reason"])

    corrected = WalletBench.get_turn!(attempt.id, :T2)

    assert corrected.judgment ==
             put_in(turn.judgment, ["criteria", "C6"], %{"value" => "false", "reason" => reason})

    assert Map.take(corrected, [:state, :evidence, :checks, :judge_cost_usd, :model_spend_usd]) ==
             Map.take(turn, [:state, :evidence, :checks, :judge_cost_usd, :model_spend_usd])

    assert WalletBench.get_attempt!(attempt.id).state == attempt.state

    assert [event] = corrections(attempt)
    assert event.operator == "tester"

    assert %{
             "criterion" => "C6",
             "from" => "true",
             "to" => "false",
             "reviewer" => "Techtree review"
           } =
             event.detail
  end

  test "run again with the same answer, it changes nothing and records no second event", %{
    attempt: attempt
  } do
    assert {:ok, %{after: once}} = correct(attempt, "C6", "false")
    assert {:ok, %{before: ^once, after: ^once}} = correct(attempt, "C6", "false")

    assert WalletBench.get_turn!(attempt.id, :T2).judgment["criteria"]["C6"] == once
    assert [_one] = corrections(attempt)
  end

  test "a check the ruling lacks, an answer outside true, false and open, or no such turn is refused",
       %{
         attempt: attempt,
         turn: turn
       } do
    assert {:error, _} = correct(attempt, "C10", "false")
    assert {:error, _} = correct(attempt, "C6", "no")

    assert {:error, _} =
             Correction.correct(
               attempt.id,
               "T3",
               "C6",
               "false",
               @reason,
               "Techtree review",
               "tester"
             )

    assert {:error, _} =
             Correction.correct(
               Ecto.UUID.generate(),
               "T2",
               "C6",
               "false",
               @reason,
               "Techtree review",
               "tester"
             )

    assert {:error, _} =
             Correction.correct(
               attempt.id,
               "T9",
               "C6",
               "false",
               @reason,
               "Techtree review",
               "tester"
             )

    # An unknown check is refused by the action itself too.
    assert {:error, _} =
             WalletBench.correct_turn_check(turn, "C10", "false", @reason, "Techtree review",
               actor: %Operator{name: "tester"},
               authorize?: false
             )

    assert WalletBench.get_turn!(attempt.id, :T2).judgment == turn.judgment
    assert corrections(attempt) == []
  end

  test "only a named operator corrects, and only a judged turn", %{attempt: attempt, turn: turn} do
    assert {:error, _} =
             WalletBench.correct_turn_check(turn, "C6", "false", @reason, "Techtree review",
               authorize?: false
             )

    assert {:error, %Ash.Error.Forbidden{}} =
             WalletBench.correct_turn_check(turn, "C6", "false", @reason, "Techtree review",
               actor: %Operator{name: "tester"}
             )

    still_running = Ash.Seed.update!(turn, %{state: :finished})

    assert {:error, _} =
             WalletBench.correct_turn_check(
               still_running,
               "C6",
               "false",
               @reason,
               "Techtree review",
               actor: %Operator{name: "tester"},
               authorize?: false
             )

    assert WalletBench.get_turn!(attempt.id, :T2).judgment == turn.judgment
    assert corrections(attempt) == []
  end

  test "the operator's command prints the check before and after, and a second run changes nothing",
       %{attempt: attempt} do
    shell = Mix.shell()
    Mix.shell(Mix.Shell.Process)
    on_exit(fn -> Mix.shell(shell) end)

    command =
      ~w(correct --attempt #{attempt.id} --test T2 --criterion C6 --value false --operator tester) ++
        ["--reason", @reason, "--reviewer", "Techtree review"]

    Mix.Task.rerun("techtree.wallet_bench", command)
    assert_received {:mix_shell, :info, [printed]}

    assert %{"before" => %{"value" => "true"}, "after" => %{"value" => "false"} = once} =
             Jason.decode!(printed)

    Mix.Task.rerun("techtree.wallet_bench", command)
    assert_received {:mix_shell, :info, [again]}
    assert %{"before" => ^once, "after" => ^once} = Jason.decode!(again)

    Mix.Task.rerun(
      "techtree.wallet_bench",
      ~w(check --attempt #{attempt.id} --test T2 --criterion C6)
    )

    assert_received {:mix_shell, :info, [checked]}
    assert Jason.decode!(checked) == once
    assert [_one] = corrections(attempt)

    assert_raise Mix.Error, fn ->
      Mix.Task.rerun(
        "techtree.wallet_bench",
        ~w(check --attempt #{attempt.id} --test T2 --criterion C10)
      )
    end
  end
end
