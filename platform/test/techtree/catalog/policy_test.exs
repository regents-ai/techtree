defmodule Techtree.Catalog.PolicyTest do
  @moduledoc """
  The read-only promise does not rest on the routing table alone.

  Even if something reached the catalog resources from outside the importer —
  a future page, a console, a transport — the resources themselves refuse every
  write. Only the importer writes, and only by bypassing authorization
  deliberately and in one place.
  """

  use Techtree.DataCase, async: true

  alias Techtree.Catalog.BootstrapRelease
  alias Techtree.Catalog.CatalogEntry
  alias Techtree.Catalog.CatalogRelease

  @resources [CatalogEntry, CatalogRelease, BootstrapRelease]

  test "reading the catalog needs no actor" do
    for resource <- @resources do
      assert Ash.can?({resource, :read}, nil)
    end
  end

  test "no write action is permitted through a public interface" do
    refute Ash.can?({CatalogEntry, :upsert_from_import, %{}}, nil)
    refute Ash.can?({CatalogEntry, :retire_missing_from_import, %{}}, nil)
    refute Ash.can?({CatalogRelease, :begin_import, %{}}, nil)
    refute Ash.can?({CatalogRelease, :complete_import, %{}}, nil)
    refute Ash.can?({CatalogRelease, :activate, %{}}, nil)
    refute Ash.can?({BootstrapRelease, :stage_from_import, %{}}, nil)
    refute Ash.can?({BootstrapRelease, :activate, %{}}, nil)
  end

  test "no resource offers a destroy action at all" do
    for resource <- @resources do
      destroys =
        resource
        |> Ash.Resource.Info.actions()
        |> Enum.filter(&(&1.type == :destroy))

      assert destroys == []
    end
  end

  test "an actor cannot be talked into a write" do
    for actor <- [%{admin: true}, %{role: :admin}, %{internal: true}] do
      refute Ash.can?({CatalogEntry, :upsert_from_import, %{}}, actor)
    end
  end
end
