defmodule Techtree.Network.PolicyTest do
  @moduledoc """
  The log's append-only promise does not rest on there being one endpoint.

  Even if something reached these resources from outside the ingest — a future
  page, a console, a live transport — the resources themselves refuse every
  write. Only `Techtree.Network.Ingest` writes, and only by bypassing
  authorization deliberately and in one place.

  The destroy actions are checked one way for the log and the other way for the
  address. A published entry has no destroy action to call at all, so a
  publication cannot be unpublished even by something holding the connection.
  An address a person volunteered is not evidence, and asking for it back has
  to take it away, so there is one there — behind the same refusal as every
  other write.

  The contributor address is checked twice over, because it is the one thing
  here that is never public: it refuses reads as well as writes, and it has no
  relationship to anything on the log, so nothing could render one by following
  an association it happened to load.
  """

  use Techtree.DataCase, async: true

  alias Techtree.Network.ContributorAddress
  alias Techtree.Network.PublicationEntry
  alias Techtree.Network.PublicationEvent

  @log [PublicationEntry, PublicationEvent]

  test "reading the log needs no actor" do
    for resource <- @log do
      assert Ash.can?({resource, :read}, nil)
    end
  end

  test "no write action is permitted through a public interface" do
    refute Ash.can?({PublicationEntry, :record, %{}}, nil)
    refute Ash.can?({PublicationEntry, :mark_withdrawn, %{}}, nil)
    refute Ash.can?({PublicationEvent, :record, %{}}, nil)
    refute Ash.can?({ContributorAddress, :record, %{}}, nil)
    refute Ash.can?({ContributorAddress, :forget, %{}}, nil)
  end

  test "a published entry offers no destroy action at all" do
    for resource <- @log do
      destroys =
        resource
        |> Ash.Resource.Info.actions()
        |> Enum.filter(&(&1.type == :destroy))

      assert destroys == []
    end
  end

  test "an address a person volunteered can be taken away, and only by the ingest" do
    assert [%{name: :forget}] =
             ContributorAddress
             |> Ash.Resource.Info.actions()
             |> Enum.filter(&(&1.type == :destroy))

    refute Ash.can?({ContributorAddress, :forget, %{}}, nil)
  end

  test "an address a person volunteered cannot even be read" do
    refute Ash.can?({ContributorAddress, :read}, nil)
    refute Ash.can?({ContributorAddress, :by_address, %{}}, nil)
  end

  test "no column of a volunteered address is public, so nothing could serialise one" do
    for attribute <- Ash.Resource.Info.attributes(ContributorAddress) do
      refute attribute.public?, "#{attribute.name} is public"
    end
  end

  test "a volunteered address is keyed by the address itself" do
    assert Ash.Resource.Info.primary_key(ContributorAddress) == [:address]
  end

  test "nothing on the log has a relationship to a volunteered address" do
    for resource <- @log do
      related =
        resource
        |> Ash.Resource.Info.relationships()
        |> Enum.map(& &1.destination)

      refute ContributorAddress in related
    end

    assert Ash.Resource.Info.relationships(ContributorAddress) == []
  end

  test "an actor cannot be talked into a write" do
    for actor <- [%{admin: true}, %{role: :admin}, %{internal: true}] do
      refute Ash.can?({PublicationEntry, :record, %{}}, actor)
      refute Ash.can?({PublicationEvent, :record, %{}}, actor)
      refute Ash.can?({ContributorAddress, :forget, %{}}, actor)
      refute Ash.can?({ContributorAddress, :read}, actor)
    end
  end

  test "the log carries the three unique rules idempotence rests on" do
    identities =
      PublicationEntry
      |> Ash.Resource.Info.identities()
      |> Map.new(&{&1.name, &1.keys})

    assert identities == %{
             unique_bundle_digest: [:bundle_digest],
             unique_log_sequence: [:log_sequence],
             unique_participant_run: [:participant_key_id, :run_id]
           }
  end
end
