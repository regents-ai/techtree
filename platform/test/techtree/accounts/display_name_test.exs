defmodule Techtree.Accounts.DisplayNameTest do
  # Every Regent site writes names to one shared profile store, one row per
  # Privy app and person. A page lists many accounts at once and reads their
  # names in one go, so each account must get the name its person set for this
  # site's app, in the order the page asked, and never a name set elsewhere.
  # The read runs on every signed request a paired agent sends, so it prints
  # nothing while it does. Not async: the check on what it prints reads the
  # whole test run's error output.
  use Techtree.DataCase, async: false
  use ExUnitProperties

  import ExUnit.CaptureIO, only: [with_io: 2]

  alias Techtree.Accounts.HumanAccount

  property "each account shows its own name for this site, never one set elsewhere" do
    check all(
            people <- list_of(person(), min_length: 1, max_length: 6),
            picks <- list_of(integer(0..(length(people) - 1)), max_length: 12)
          ) do
      people = Enum.map(people, &Map.put(&1, :did, "did:privy:#{System.unique_integer()}"))
      store(people)

      accounts =
        Enum.map(picks, &%HumanAccount{id: &1, privy_user_id: Enum.at(people, &1).did})

      {names, printed} =
        with_io(:stderr, fn ->
          accounts |> Ash.load!(:display_name, authorize?: false) |> Enum.map(& &1.display_name)
        end)

      assert names == Enum.map(picks, &Enum.at(people, &1).here)
      assert printed == ""
    end
  end

  # A person with or without a name on this site, and on another site.
  defp person do
    fixed_map(%{
      here: one_of([constant(nil), name()]),
      elsewhere: one_of([constant(nil), name()])
    })
  end

  defp name, do: string(:alphanumeric, min_length: 1, max_length: 80)

  defp store(people) do
    now = DateTime.utc_now()

    rows =
      for person <- people,
          {app_id, name} <- [{"test-app", person.here}, {"other-app", person.elsewhere}],
          name != nil do
        %{
          id: Ecto.UUID.bingenerate(),
          app_id: app_id,
          privy_user_id: person.did,
          display_name: name,
          wallet_addresses: [],
          proof_issued_at: 0,
          inserted_at: now,
          updated_at: now
        }
      end

    Repo.insert_all("profiles", rows, prefix: "regent_identity")
  end
end
