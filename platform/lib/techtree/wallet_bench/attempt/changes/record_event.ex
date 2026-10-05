defmodule Techtree.WalletBench.Attempt.Changes.RecordEvent do
  @moduledoc """
  Appends an attempt's or a turn's new state to the attempt's events, in the
  same transaction. A step puts what it saw under the changeset context's
  `:event_detail` (`put_detail/2`).
  """

  use Ash.Resource.Change

  alias Techtree.WalletBench.{Attempt, Catalog, Turn}

  @impl true
  def change(changeset, _opts, _context) do
    Ash.Changeset.after_action(changeset, fn changeset, record ->
      {attempt_id, step} = step(record)

      Techtree.WalletBench.AttemptEvent
      |> Ash.Changeset.for_create(:record, %{
        attempt_id: attempt_id,
        step: step,
        detail: Map.get(changeset.context, :event_detail, %{})
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

  defp step(%Attempt{id: id, state: state}), do: {id, Atom.to_string(state)}

  defp step(%Turn{attempt_id: attempt_id, test: test, state: state}),
    do: {attempt_id, Catalog.turn_name(test) <> " " <> Atom.to_string(state)}
end
