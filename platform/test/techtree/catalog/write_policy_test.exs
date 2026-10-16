defmodule Techtree.Catalog.WritePolicyTest do
  use Techtree.DataCase, async: true

  alias Techtree.Actors.System
  alias Techtree.Catalog.{BootstrapRelease, CatalogEntry, CatalogRelease}

  test "only the site's own machinery may write the catalog" do
    for resource <- [BootstrapRelease, CatalogEntry, CatalogRelease],
        action <- Ash.Resource.Info.actions(resource),
        action.type != :read do
      assert Ash.can?({resource, action.name}, %System{}),
             "#{inspect(resource)}.#{action.name} refuses the system actor"

      refute Ash.can?({resource, action.name}, %{role: :system}),
             "#{inspect(resource)}.#{action.name} admits a map that only claims the system role"
    end
  end
end
