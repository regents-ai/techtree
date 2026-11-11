defmodule Techtree.Watchdog.OwnershipTest do
  @moduledoc """
  The ownership check: both proof methods against a stubbed resolver and site
  (`Req.Test`), the guard that refuses to fetch from anything but a public
  address, and the fetch going to the address that was checked, so the one
  request Watchdog makes can never reach inward. Only a proof that is
  positively missing reads as `:proof_missing`; a check that could not be made
  says so.
  """

  use ExUnit.Case, async: false

  alias Techtree.Watchdog.Ownership
  alias Techtree.WatchdogFixture

  @env Techtree.Watchdog.Ownership

  # Answers a request with the proof and hands the request it was given back
  # to the test, which runs in the same process.
  defmodule CaptureAdapter do
    def run(request) do
      send(self(), {:fetched, request})
      body = "techtree-watchdog-verification=tok-123"
      {request, Req.Response.new(status: 200, body: body)}
    end
  end

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
      Req.Test.json(conn, WatchdogFixture.dns_answer(["techtree-watchdog-verification=tok-123"]))
    end)

    assert Ownership.verify(host(:dns_txt)) == :ok
  end

  test "a DNS answer without the record is a missing proof" do
    stub(fn conn -> Req.Test.json(conn, WatchdogFixture.dns_answer(["v=spf1 -all"])) end)
    assert Ownership.verify(host(:dns_txt)) == {:error, :proof_missing}
  end

  test "a name with no DNS records at all is a missing proof" do
    stub(fn conn -> Req.Test.json(conn, %{"Status" => 3}) end)
    assert Ownership.verify(host(:dns_txt)) == {:error, :proof_missing}
  end

  test "the DNS check reads the resolver, never the customer's host" do
    stub(fn conn ->
      assert conn.host == "dns.google"
      Req.Test.json(conn, WatchdogFixture.dns_answer([]))
    end)

    assert Ownership.verify(host(:dns_txt)) == {:error, :proof_missing}
  end

  test "a failed lookup or an unreachable resolver is not a missing proof" do
    stub(fn conn -> Req.Test.json(conn, %{"Status" => 2}) end)
    assert Ownership.verify(host(:dns_txt)) == {:error, :resolver_failed}

    stub(fn conn -> Req.Test.transport_error(conn, :timeout) end)
    assert Ownership.verify(host(:dns_txt)) == {:error, :resolver_unreachable}
  end

  test "a well-known file that matches proves the host" do
    stub(fn conn ->
      assert conn.host == "1.1.1.1"
      assert conn.request_path == "/.well-known/techtree-watchdog.txt"
      Req.Test.text(conn, "techtree-watchdog-verification=tok-123\n")
    end)

    assert Ownership.verify(host(:well_known_file)) == :ok
  end

  test "the file is fetched from the checked address under the host's own name" do
    for {address, url_host} <- [
          {{93, 184, 216, 34}, "93.184.216.34"},
          {{0x2606, 0x2800, 0, 0, 0, 0, 0, 1}, "2606:2800::1"}
        ] do
      Application.put_env(:techtree, @env,
        resolver: fn "proven.example" -> [address] end,
        req_options: [adapter: CaptureAdapter]
      )

      assert Ownership.verify(host(:well_known_file)) == :ok
      assert_received {:fetched, request}
      assert request.url.host == url_host
      assert request.url.path == "/.well-known/techtree-watchdog.txt"
      assert request.options.connect_options[:hostname] == "proven.example"
      assert request.options.redirect == false
      assert request.options.retry == false
    end
  end

  test "a well-known file with the wrong contents is a missing proof" do
    stub(fn conn -> Req.Test.text(conn, "nope") end)
    assert Ownership.verify(host(:well_known_file)) == {:error, :proof_missing}
  end

  test "a well-known file that is missing is a missing proof" do
    stub(fn conn -> conn |> Plug.Conn.put_status(404) |> Req.Test.text("not found") end)
    assert Ownership.verify(host(:well_known_file)) == {:error, :proof_missing}
  end

  test "a site that errors or cannot be reached is not a missing proof" do
    stub(fn conn -> conn |> Plug.Conn.put_status(503) |> Req.Test.text("busy") end)
    assert Ownership.verify(host(:well_known_file)) == {:error, {:file_status, 503}}

    stub(fn conn -> Req.Test.transport_error(conn, :timeout) end)
    assert Ownership.verify(host(:well_known_file)) == {:error, :host_unreachable}
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
