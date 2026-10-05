defmodule Techtree.WalletBench.Turn.Changes.Advance do
  @moduledoc """
  After a turn is judged or fails, in the same transaction: queues the next
  test, ends the attempt's tests, or stops the attempt. A turn that only moved
  on to `finished` changes nothing.

  - T1a passed, or T1b passed: T2, continuing the same conversation.
  - T1a not passed and the judge named an error to send back: T1b with it.
  - T2 signed but never printed the signature: the signature request.
  - Anything else ends the tests; a failed turn stops the attempt with its reason.
  """

  use Ash.Resource.Change

  alias Techtree.WalletBench.{Attempt, Catalog, Turn}

  @impl true
  def change(changeset, _opts, _context) do
    Ash.Changeset.after_action(changeset, fn
      _changeset, %Turn{state: state} = turn when state in [:judged, :failed] ->
        with {:ok, attempt} <- Ash.get(Attempt, turn.attempt_id),
             {:ok, _record} <- advance(attempt, turn) do
          {:ok, turn}
        end

      _changeset, turn ->
        {:ok, turn}
    end)
  end

  defp advance(attempt, %Turn{state: :failed} = turn) do
    update(attempt, :stop, %{error: Catalog.turn_name(turn.test) <> ": " <> turn.failure})
  end

  defp advance(attempt, %Turn{state: :judged} = turn) do
    case next(turn.test, turn.judgment) do
      {test, error} -> queue(attempt, turn, test, error)
      :done -> update(attempt, :finish_tests, %{})
    end
  end

  defp next(:T1a, %{"outcome" => "PASS"}), do: {:T2, nil}
  defp next(:T1a, %{"retry_error" => error}) when error != "", do: {:T1b, error}
  defp next(:T1b, %{"outcome" => "PASS"}), do: {:T2, nil}
  defp next(:T2, %{"signature_needed" => true}), do: {:T2_signature, nil}
  defp next(_test, _judgment), do: :done

  defp queue(attempt, turn, test, error) do
    Turn
    |> Ash.Changeset.for_create(:queue, %{
      attempt_id: attempt.id,
      test: test,
      prompt: Catalog.prompt(test, attempt.harness_id, attempt.wallet_id, error),
      resume_session_id: turn.session_id
    })
    # The turn's own step queues the next; turns have no public writer.
    |> Ash.create(authorize?: false)
  end

  defp update(attempt, action, arguments) do
    attempt
    |> Ash.Changeset.for_update(action, arguments)
    # Attempts have no public writer; the turn's own job moving its attempt on
    # is one of the few.
    |> Ash.update(authorize?: false)
  end
end
