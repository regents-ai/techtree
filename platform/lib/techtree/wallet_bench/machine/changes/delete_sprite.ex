defmodule Techtree.WalletBench.Machine.Changes.DeleteSprite do
  @moduledoc """
  Deletes the machine and its checkpoints on Sprites. A machine Sprites no
  longer has is already gone.
  """

  use Ash.Resource.Change

  @impl true
  def change(changeset, _opts, _context) do
    Ash.Changeset.before_transaction(changeset, fn changeset ->
      case RegentSprites.delete(changeset.data.name) do
        :ok -> changeset
        {:error, %RegentSprites.Error{reason: {:sprites, 404, _message}}} -> changeset
        {:error, error} -> Ash.Changeset.add_error(changeset, error)
      end
    end)
  end
end
