defmodule Techtree.WalletBench.Attempt.Changes.RevokeCredentials do
  @moduledoc """
  Takes the model key off the machine: stops the translator and deletes the key
  file (`credentials.sh revoke`), and succeeds only when both are confirmed
  gone. Revoking again finds nothing to remove and succeeds.
  """

  use Ash.Resource.Change

  import Techtree.WalletBench.Attempt.Changes.RecordEvent, only: [put_detail: 2]

  alias Techtree.WalletBench.{Machine, Remote}

  @impl true
  def change(changeset, _opts, _context) do
    Ash.Changeset.before_transaction(changeset, fn changeset ->
      with {:ok, machine} <- Ash.get(Machine, changeset.data.machine_id),
           {:ok, "revoked\n"} <-
             Remote.run(machine.name, ["bash", "/work/bin/machine/credentials.sh", "revoke"],
               receive_timeout: 120_000
             ) do
        put_detail(changeset, %{credentials: "revoked"})
      else
        {:ok, other} ->
          Ash.Changeset.add_error(changeset, "credentials.sh revoke printed #{inspect(other)}")

        {:error, error} ->
          Ash.Changeset.add_error(changeset, error)
      end
    end)
  end
end
