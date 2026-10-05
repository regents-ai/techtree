defmodule Techtree.WalletBench.Machine.Changes.RecordEvent do
  @moduledoc """
  Appends the machine's new state to its events, in the same transaction.

  A step puts what it saw under the changeset context's `:event_detail`. With
  `argument: name`, the action's argument of that name is added to it.
  """

  use Ash.Resource.Change

  @impl true
  def change(changeset, opts, _context) do
    changeset =
      case opts[:argument] do
        nil -> changeset
        name -> put_detail(changeset, %{name => Ash.Changeset.get_argument(changeset, name)})
      end

    Ash.Changeset.after_action(changeset, fn changeset, machine ->
      Techtree.WalletBench.MachineEvent
      |> Ash.Changeset.for_create(:record, %{
        machine_id: machine.id,
        step: machine.state,
        detail: Map.get(changeset.context, :event_detail, %{})
      })
      # Events have no public writer; this step, inside the machine's own
      # authorized action, is the only one.
      |> Ash.create(authorize?: false)
      |> case do
        {:ok, _event} -> {:ok, machine}
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
end
