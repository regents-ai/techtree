defmodule Techtree.WalletBench.Attempt.Changes.ReleaseMachine do
  @moduledoc """
  Gives the attempt's machine back in the attempt's own transaction: `to:
  :reset` once the key is confirmed gone, `to: :retire` when it could not be.
  """

  use Ash.Resource.Change

  alias Techtree.WalletBench.Machine

  @impl true
  def change(changeset, opts, _context) do
    Ash.Changeset.after_action(changeset, fn _changeset, attempt ->
      with {:ok, machine} <- Ash.get(Machine, attempt.machine_id),
           {:ok, _machine} <-
             machine
             |> Ash.Changeset.for_update(opts[:to], arguments(opts[:to], attempt))
             # The attempt's own step, inside its authorized action.
             |> Ash.update(authorize?: false) do
        {:ok, attempt}
      end
    end)
  end

  defp arguments(:reset, attempt), do: %{attempt_id: attempt.id}
  defp arguments(:retire, attempt), do: %{reason: "Attempt #{attempt.id}: #{attempt.failure}"}
end
