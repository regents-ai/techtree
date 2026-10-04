defmodule Techtree.WalletBench.Machine.Changes.CreateSprite do
  @moduledoc """
  Creates the machine on Sprites. A name already in use there is looked up
  instead, so a repeated job finds the machine its earlier run made.
  """

  use Ash.Resource.Change

  import Techtree.WalletBench.Machine.Changes.RecordEvent, only: [put_detail: 2]

  @impl true
  def change(changeset, _opts, _context) do
    Ash.Changeset.before_transaction(changeset, fn changeset ->
      name = changeset.data.name

      case create_or_get(name) do
        {:ok, %RegentSprites.Sprite{name: ^name} = sprite} ->
          changeset
          |> Ash.Changeset.force_change_attributes(%{
            sprite_id: sprite.id,
            sprite_version: sprite.version,
            environment_version: sprite.environment_version
          })
          |> put_detail(%{
            sprite_id: sprite.id,
            sprite_version: sprite.version,
            environment_version: sprite.environment_version
          })

        {:ok, %RegentSprites.Sprite{name: other}} ->
          Ash.Changeset.add_error(changeset, "Sprites answered with machine #{other}")

        {:error, error} ->
          Ash.Changeset.add_error(changeset, error)
      end
    end)
  end

  defp create_or_get(name) do
    case RegentSprites.create(name) do
      {:error, %RegentSprites.Error{reason: {:sprites, 409, _message}}} -> RegentSprites.get(name)
      result -> result
    end
  end
end
