defmodule Techtree.WalletBench.Attempt.Changes.SignFunding do
  @moduledoc """
  Signs the attempt's two funding sends (`Techtree.WalletBench.Funding.prepare/1`)
  before the transaction opens, then keeps them as `signed` payments in the same
  transaction as the attempt's move to `sending`; nothing is broadcast yet.
  When the bench cannot fund it (funding paused, the run's total reached, the
  funder short), the attempt stops as a bench failure, with the reason: it
  leaves the results, as any run the bench itself spoiled does.

  The sends are kept only after `Techtree.WalletBench.Funding.admit/1` finds
  the run's totals still have room for them. When another attempt's funding
  took that room after these were signed, nothing is kept and the step fails;
  its retry prepares again and is refused with the reason.
  """

  use Ash.Resource.Change

  import Techtree.WalletBench.Attempt.Changes.RecordEvent, only: [put_detail: 2]

  alias Techtree.WalletBench.{Funding, Payment}

  @impl true
  def change(changeset, _opts, _context) do
    Ash.Changeset.before_transaction(changeset, fn changeset ->
      prepared(changeset, Funding.prepare(changeset.data.agent_address))
    end)
  end

  defp prepared(changeset, {:ok, sends}) do
    changeset
    |> Ash.Changeset.force_change_attribute(:state, :sending)
    |> put_detail(%{sends: Enum.map(sends, &Map.take(&1, [:token, :amount, :nonce, :hash]))})
    |> Ash.Changeset.after_action(fn _changeset, attempt -> keep(attempt, sends) end)
  end

  defp prepared(changeset, {:refuse, reason}) do
    changeset
    |> Ash.Changeset.force_change_attributes(%{state: :revoking, failure: reason})
    |> put_detail(%{failure: reason})
  end

  defp prepared(changeset, {:error, error}), do: Ash.Changeset.add_error(changeset, error)

  defp keep(attempt, sends) do
    case Funding.admit(sends) do
      :ok -> create(attempt, sends)
      {:refuse, reason} -> {:error, reason}
    end
  end

  defp create(attempt, sends) do
    Enum.reduce_while(sends, {:ok, attempt}, fn send, {:ok, attempt} ->
      Payment
      |> Ash.Changeset.for_create(:sign, Map.put(send, :attempt_id, attempt.id))
      # Payments have no public writer; the attempt's own funding step is one of two.
      |> Ash.create(authorize?: false)
      |> case do
        {:ok, _payment} -> {:cont, {:ok, attempt}}
        {:error, error} -> {:halt, {:error, error}}
      end
    end)
  end
end
