defmodule Techtree.Watchdog.OwnershipTest do
  @moduledoc """
  The ownership check: both proof methods against a stubbed resolver and site
  (`Req.Test`), and the guard that refuses to fetch from anything but a public
  address, so the one request Watchdog makes can never reach inward.
  """

  use ExUnit.Case, async: false

  alias Techtree.Watchdog.Ownership

  @env Techtree.Watchdog.Ownership

  setup do
    on_exit(fn -> Application.delete_env(:techtree, @env) end)
    :ok
  end

  defp host(method, origin \\ "proven.example"),
    do: %{ownership_method: method, origin: origin, verification_token: "tok-123"}

  defp stub(fun, resolver \\ fn _origin -> [{1, 1, 1, 1}] end) do
    Application.put_env(:techtree, @env,
      req_options: [plug: {Req.Test, @env}],
      resolver: resolver
    )

    Req.Test.stub(@env, fun)
  end

  test "a DNS TXT record that matches proves the host" do
    stub(fn conn ->
      assert conn.host == "dns.google"

      Req.Test.json(conn, %{
        "Answer" => [%{"type" => 16, "data" => ~s("techtree-watchdog-verification=tok-123")}]
      })
    end)

    assert Ownership.verify(host(:dns_txt)) == :ok
  end

  test "a DNS answer without the record is not proof" do
    stub(fn conn ->
      Req.Test.json(conn, %{"Answer" => [%{"type" => 16, "data" => ~s("v=spf1 -all")}]})
    end)

    assert Ownership.verify(host(:dns_txt)) == {:error, :record_not_found}
  end

  test "the DNS check reads the resolver, never the customer's host" do
    stub(fn conn ->
      assert conn.host == "dns.google"
      Req.Test.json(conn, %{"Answer" => []})
    end)

    assert Ownership.verify(host(:dns_txt)) == {:error, :record_not_found}
  end

  test "a well-known file that matches proves the host" do
    stub(fn conn ->
      assert conn.host == "proven.example"
      assert conn.request_path == "/.well-known/techtree-watchdog.txt"
      Req.Test.text(conn, "techtree-watchdog-verification=tok-123\n")
    end)

    assert Ownership.verify(host(:well_known_file)) == :ok
  end

  test "a well-known file with the wrong contents is not proof" do
    stub(fn conn -> Req.Test.text(conn, "nope") end)
    assert Ownership.verify(host(:well_known_file)) == {:error, :record_not_found}
  end

  test "a well-known file that is missing is not proof" do
    stub(fn conn -> conn |> Plug.Conn.put_status(404) |> Req.Test.text("not found") end)
    assert Ownership.verify(host(:well_known_file)) == {:error, {:file_status, 404}}
  end

  test "a private or local host is refused before any request is sent" do
    stub(fn _conn -> raise "the guard should have stopped this request" end)

    for origin <- [
          "127.0.0.1",
          "10.0.0.9",
          "192.168.1.1",
          "169.254.169.254",
          "::1",
          "localhost",
          "box.internal"
        ] do
      assert Ownership.verify(host(:well_known_file, origin)) == {:error, :host_not_public},
             "expected #{origin} to be refused"
    end
  end

  test "a name that resolves only to a private address is refused" do
    stub(
      fn _conn -> raise "the guard should have stopped this request" end,
      fn _origin -> [{10, 0, 0, 5}] end
    )

    assert Ownership.verify(host(:well_known_file, "inside.example")) ==
             {:error, :host_not_public}
  end

  test "public_host? judges literals without resolving" do
    assert Ownership.public_host?("1.1.1.1")
    refute Ownership.public_host?("127.0.0.1")
    refute Ownership.public_host?("172.16.3.3")
    refute Ownership.public_host?("fd00::1")
    refute Ownership.public_host?("")
  end
end
