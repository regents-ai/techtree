defmodule Techtree.WatchdogTest do
  @moduledoc """
  Watchdog's resources: a person keeps only their own list, the caps hold,
  routes stay on their own proven hosts, and a check proves or revokes a host.
  """

  use Techtree.DataCase, async: false
  use Oban.Testing, repo: Techtree.Repo

  alias Techtree.Watchdog
  alias Techtree.Watchdog.{Host, Ownership, Route}
  alias Techtree.WatchdogFixture

  setup do
    [owner: WatchdogFixture.person!(), other: WatchdogFixture.person!()]
  end

  defp add_host!(actor, origin \\ "example.com", method \\ :dns_txt) do
    {:ok, host} = Watchdog.add_host(origin, %{ownership_method: method}, actor: actor)
    host
  end

  defp prove!(host, actor) do
    WatchdogFixture.stub_ownership(fn conn ->
      Req.Test.json(conn, %{
        "Answer" => [%{"type" => 16, "data" => ~s("#{Ownership.record_value(host)}")}]
      })
    end)

    {:ok, proven} = Ash.update(host, %{}, action: :check_ownership, actor: actor)
    proven
  end

  describe "hosts" do
    test "a new host is unproven, carries a token and gives the right proof record", %{
      owner: owner
    } do
      host = add_host!(owner, "Example.com")

      assert host.origin == "example.com"
      assert host.ownership_state == :unverified
      assert String.starts_with?(Ownership.record_value(host), "techtree-watchdog-verification=")
      assert Ownership.txt_name(host) == "example.com"

      assert Ownership.well_known_url(host) ==
               "https://example.com/.well-known/techtree-watchdog.txt"
    end

    test "the host is read out of a full URL, lowercased, without a path", %{owner: owner} do
      assert add_host!(owner, "https://Shop.Example.com/login?x=1").origin == "shop.example.com"
    end

    test "junk is refused", %{owner: owner} do
      assert {:error, %Ash.Error.Invalid{}} =
               Watchdog.add_host("not a host", %{ownership_method: :dns_txt}, actor: owner)
    end

    test "only the owner sees or changes their host", %{owner: owner, other: other} do
      host = add_host!(owner)

      assert Watchdog.list_my_hosts!(actor: owner) |> Enum.map(& &1.id) == [host.id]
      assert Watchdog.list_my_hosts!(actor: other) == []
      assert {:error, _not_found} = Ash.get(Host, host.id, actor: other)
      assert {:error, %Ash.Error.Forbidden{}} = Watchdog.remove_host(host, actor: other)

      assert {:error, %Ash.Error.Forbidden{}} =
               Watchdog.request_host_verification(host, actor: other)
    end

    test "the host cap holds and counts only this account", %{owner: owner, other: other} do
      with_caps(hosts: 2, routes: 100)

      add_host!(owner, "one.example")
      add_host!(owner, "two.example")
      add_host!(other, "theirs.example")

      assert {:error, %Ash.Error.Invalid{} = error} =
               Watchdog.add_host("three.example", %{ownership_method: :dns_txt}, actor: owner)

      assert Exception.message(error) =~ "most sites"
    end
  end

  describe "proving ownership" do
    test "a matching proof makes the host proven; losing it revokes it", %{owner: owner} do
      host = add_host!(owner)

      proven = prove!(host, owner)
      assert proven.ownership_state == :verified
      assert proven.verified_at

      WatchdogFixture.stub_ownership(fn conn ->
        Req.Test.json(conn, %{"Answer" => []})
      end)

      {:ok, revoked} = Ash.update(proven, %{}, action: :check_ownership, actor: owner)
      assert revoked.ownership_state == :revoked
    end

    test "requesting a check marks it pending and enqueues the check job", %{owner: owner} do
      host = add_host!(owner)
      {:ok, pending} = Watchdog.request_host_verification(host, actor: owner)

      assert pending.ownership_state == :pending
      assert_enqueued(worker: Techtree.Watchdog.Host.Workers.CheckOwnership)
    end
  end

  describe "routes" do
    test "a route on an unproven host starts off; proving lets it be turned on", %{owner: owner} do
      host = add_host!(owner)
      {:ok, route} = Watchdog.add_route(host.id, %{url: "https://example.com/pay"}, actor: owner)
      assert route.kind == :public
      assert route.state == :paused

      assert {:error, %Ash.Error.Invalid{}} = Watchdog.resume_route(route, actor: owner)

      prove!(host, owner)
      {:ok, active} = Watchdog.resume_route(route, actor: owner)
      assert active.state == :active
    end

    test "a route on a proven host starts active", %{owner: owner} do
      host = owner |> add_host!() |> prove!(owner)
      {:ok, route} = Watchdog.add_route(host.id, %{url: "https://example.com/a"}, actor: owner)
      assert route.state == :active
    end

    test "a route must sit on its host and be a web address", %{owner: owner} do
      host = add_host!(owner)

      assert {:error, %Ash.Error.Invalid{}} =
               Watchdog.add_route(host.id, %{url: "https://elsewhere.example/x"}, actor: owner)

      assert {:error, %Ash.Error.Invalid{}} =
               Watchdog.add_route(host.id, %{url: "not-a-url"}, actor: owner)
    end

    test "a route can't be hung off someone else's host", %{owner: owner, other: other} do
      host = add_host!(owner)

      assert {:error, %Ash.Error.Invalid{}} =
               Watchdog.add_route(host.id, %{url: "https://example.com/x"}, actor: other)
    end

    test "only the owner sees or changes their routes", %{owner: owner, other: other} do
      host = add_host!(owner)
      {:ok, route} = Watchdog.add_route(host.id, %{url: "https://example.com/x"}, actor: owner)

      assert Watchdog.list_my_routes!(actor: owner) |> Enum.map(& &1.id) == [route.id]
      assert Watchdog.list_my_routes!(actor: other) == []
      assert {:error, %Ash.Error.Forbidden{}} = Watchdog.pause_route(route, actor: other)
      assert {:error, %Ash.Error.Forbidden{}} = Watchdog.remove_route(route, actor: other)
    end

    test "the route cap holds across the account's hosts", %{owner: owner} do
      with_caps(hosts: 100, routes: 2)
      host = add_host!(owner)

      {:ok, _} = Watchdog.add_route(host.id, %{url: "https://example.com/a"}, actor: owner)
      {:ok, _} = Watchdog.add_route(host.id, %{url: "https://example.com/b"}, actor: owner)

      assert {:error, %Ash.Error.Invalid{} = error} =
               Watchdog.add_route(host.id, %{url: "https://example.com/c"}, actor: owner)

      assert Exception.message(error) =~ "most addresses"
    end

    test "removing a host removes its routes", %{owner: owner} do
      host = add_host!(owner)
      {:ok, _route} = Watchdog.add_route(host.id, %{url: "https://example.com/x"}, actor: owner)

      :ok = Watchdog.remove_host(host, actor: owner)
      assert Watchdog.list_my_routes!(actor: owner) == []
      assert Ash.count!(Route, authorize?: false) == 0
    end
  end

  defp with_caps(hosts: hosts, routes: routes) do
    previous = Application.get_env(:techtree, Techtree.Watchdog)

    Application.put_env(:techtree, Techtree.Watchdog,
      max_hosts_per_account: hosts,
      max_routes_per_account: routes
    )

    on_exit(fn -> Application.put_env(:techtree, Techtree.Watchdog, previous) end)
  end
end
