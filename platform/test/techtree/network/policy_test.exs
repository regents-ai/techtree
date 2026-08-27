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
  """

  use Techtree.DataCase, async: true

  alias Techtree.Network.ContributorAddress
  alias Techtree.Network.Submission
  alias Techtree.Network.Withdrawal

  @resources [Submission, Withdrawal, ContributorAddress]

  test "reading the log needs no actor" do
    for resource <- @resources do
      assert Ash.can?({resource, :read}, nil)
    end
  end

  test "no write action is permitted through a public interface" do
    refute Ash.can?({Submission, :record, %{}}, nil)
    refute Ash.can?({Submission, :mark_withdrawn, %{}}, nil)
    refute Ash.can?({Withdrawal, :record, %{}}, nil)
    refute Ash.can?({ContributorAddress, :record, %{}}, nil)
    refute Ash.can?({ContributorAddress, :forget, %{}}, nil)
  end

  test "a published entry offers no destroy action at all" do
    for resource <- [Submission, Withdrawal] do
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

  test "an actor cannot be talked into a write" do
    for actor <- [%{admin: true}, %{role: :admin}, %{internal: true}] do
      refute Ash.can?({Submission, :record, %{}}, actor)
      refute Ash.can?({Withdrawal, :record, %{}}, actor)
      refute Ash.can?({ContributorAddress, :forget, %{}}, actor)
    end
  end
end
