defmodule Techtree.WalletBench.Attempt.Changes.RecordEvent do
  @moduledoc """
  Appends an attempt's or a turn's new state to the attempt's events, in the
  same transaction. A step puts what it saw under the changeset context's
  `:event_detail` (`put_detail/2`). With `step: name`, the event is that named
  step instead of the new state, for an action that leaves the state as it was;
  with `as: word`, a turn's event is its turn and that word, such as
  `T2 corrected`.
  """

  use Ash.Resource.Change

  alias Techtree.WalletBench.{Attempt, Catalog, Turn}

  @impl true
  def change(changeset, opts, _context) do
    Ash.Changeset.after_action(changeset, fn changeset, record ->
      {attempt_id, state_step} = step(record, opts[:as])
      step = Keyword.get(opts, :step, state_step)

      Techtree.WalletBench.AttemptEvent
      |> Ash.Changeset.for_create(:record, %{
        attempt_id: attempt_id,
        step: step,
        detail: Map.get(changeset.context, :event_detail, %{}),
        operator: Map.get(changeset.context, :operator)
      })
      # Events have no public writer; this step, inside the attempt's or turn's
      # own authorized action, is the only one.
      |> Ash.create(authorize?: false)
      |> case do
        {:ok, _event} -> {:ok, record}
        {:error, error} -> {:error, error}
      end
    end)
  end

  @doc "Adds what a step saw where `RecordEvent` finds it."
  @spec put_detail(Ash.Changeset.t(), map()) :: Ash.Changeset.t()
  def put_detail(changeset, detail) do
    detail = changeset.context |> Map.get(:event_detail, %{}) |> Map.merge(detail)
    Ash.Changeset.set_context(changeset, %{event_detail: detail})
  end

  defp step(%Attempt{id: id, state: state}, nil), do: {id, Atom.to_string(state)}

  defp step(%Turn{attempt_id: attempt_id, test: test, state: state}, as),
    do: {attempt_id, Catalog.turn_name(test) <> " " <> (as || Atom.to_string(state))}
end
