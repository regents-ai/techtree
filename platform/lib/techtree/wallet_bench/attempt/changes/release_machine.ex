defmodule Techtree.WalletBench.Attempt.Changes.ReleaseMachine do
  @moduledoc """
  Gives the attempt's machine back in the attempt's own transaction. Bankr
  machines always retire to remove credential copies from raw logs; other
  machines reset once credentials are gone, or retire when removal failed.
  """

  use Ash.Resource.Change

  alias Techtree.WalletBench.Machine

  @impl true
  def change(changeset, opts, _context) do
    Ash.Changeset.after_action(changeset, fn _changeset, attempt ->
      # Bankr's supplied key may also have reached raw harness logs. Retiring
      # W01 machines avoids preserving those copies in a restore checkpoint.
      to = if attempt.wallet_id == "W01", do: :retire, else: opts[:to]

      with {:ok, machine} <- Ash.get(Machine, attempt.machine_id),
           {:ok, _machine} <-
             machine
             |> Ash.Changeset.for_update(to, arguments(to, attempt))
             # The attempt's own step, inside its authorized action.
             |> Ash.update(authorize?: false) do
        {:ok, attempt}
      end
    end)
  end

  defp arguments(:reset, attempt), do: %{attempt_id: attempt.id}

  defp arguments(:retire, %{wallet_id: "W01", failure: nil}),
    do: %{reason: "Bankr test completed; retire the machine to remove credential copies."}

  defp arguments(:retire, attempt), do: %{reason: "Attempt #{attempt.id}: #{attempt.failure}"}
end
