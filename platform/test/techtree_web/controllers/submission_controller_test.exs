defmodule TechtreeWeb.SubmissionControllerTest do
  @moduledoc """
  The one address that accepts anything, exercised the way a caller would.

  The limits are tested by exceeding them rather than by reading the numbers
  back out of the configuration, because a test that asks the code what its own
  limit is agrees with the code no matter what the limit does.

  Each test speaks from its own address. The rate limiter counts per caller and
  the counting is real, so tests that all claimed to be the same caller would be
  each other's second attempt.
  """

  use TechtreeWeb.ConnCase, async: false

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture
  alias Techtree.Network
  alias Techtree.Network.Ingest
  alias Techtree.NetworkFixture

  @address "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"

  setup %{conn: conn} do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())

    {:ok, conn: from_own_address(conn)}
  end

  describe "publishing a run" do
    test "a real bundle is accepted, and the receipt says what was checked", %{conn: conn} do
      conn = publish(conn, NetworkFixture.submission())

      assert conn.status == 201

      body = json_response(conn, 201)

      assert body["sequence"] >= 1
      assert body["bundle_digest"] == NetworkFixture.bundle_digest()
      assert body["checks_run"] == 8
      assert body["checks_passed"] == 8
      assert body["location"] == "/api/v1/submissions/#{NetworkFixture.bundle_digest()}"

      assert get_resp_header(conn, "location") == [body["location"]]
    end

    test "the same bundle again is the same entry, not a second one", %{conn: conn} do
      first = conn |> publish(NetworkFixture.submission()) |> json_response(201)

      again =
        conn
        |> recycle()
        |> from_own_address()
        |> publish(NetworkFixture.submission())

      assert again.status == 200
      assert json_response(again, 200)["sequence"] == first["sequence"]
      assert length(Network.list_submissions!()) == 1
    end

    test "a bundle that fails a check is refused by name, in the shared error shape",
         %{conn: conn} do
      files = NetworkFixture.replace("data-policy.json", ~s({"tampered":true}))
      conn = publish(conn, NetworkFixture.submission(files))

      assert conn.status == 422

      assert %{
               "error" => %{
                 "code" => "submission_artifact_digest_mismatch",
                 "retryable" => false,
                 "message" => message
               }
             } = json_response(conn, 422)

      assert message =~ "not the file the bundle says it is"
      assert Network.list_submissions!() == []
    end

    test "a body that is not JSON at all is refused before anything is read", %{conn: conn} do
      conn =
        conn
        |> put_req_header("content-type", "application/octet-stream")
        |> post("/api/v1/submissions", "nothing here is a proof")

      assert conn.status == 400
      assert %{"error" => %{"code" => "submission_malformed"}} = json_response(conn, 400)
    end
  end

  describe "the body cap" do
    test "a body over it is refused at the parser, before it is decoded", %{conn: conn} do
      oversized =
        Jason.encode!(%{
          "schema_version" => "techtree.submission.v1alpha1",
          "files" => %{"bundle.json" => String.duplicate("a", 5_000_000)}
        })

      refused =
        assert_raise Plug.Parsers.RequestTooLargeError, fn ->
          publish(conn, oversized)
        end

      assert Plug.Exception.status(refused) == 413
      assert Network.list_submissions!() == []
    end

    test "a body under it reaches the checks", %{conn: conn} do
      assert publish(conn, NetworkFixture.submission()).status == 201
    end
  end

  describe "the rate limit" do
    test "one caller sending run after run is asked to wait" do
      caller = own_address()
      body = ~s({"schema_version":"techtree.submission.v1alpha1","files":{}})

      statuses =
        for _attempt <- 1..12 do
          Phoenix.ConnTest.build_conn()
          |> Map.put(:remote_ip, caller)
          |> publish(body)
          |> Map.fetch!(:status)
        end

      assert Enum.count(statuses, &(&1 == 400)) == 10
      assert Enum.count(statuses, &(&1 == 429)) == 2
    end

    test "the refusal says retrying could help, and roughly when" do
      caller = own_address()
      body = ~s({"schema_version":"techtree.submission.v1alpha1","files":{}})

      refused =
        Enum.reduce(1..12, nil, fn _attempt, _previous ->
          Phoenix.ConnTest.build_conn()
          |> Map.put(:remote_ip, caller)
          |> publish(body)
        end)

      assert refused.status == 429

      assert %{"error" => %{"code" => "submission_rate_limited", "retryable" => true}} =
               json_response(refused, 429)

      assert [seconds] = get_resp_header(refused, "retry-after")
      assert String.to_integer(seconds) > 0
    end

    test "another caller is unaffected by the first one's flood", %{conn: conn} do
      flooder = own_address()
      body = ~s({"schema_version":"techtree.submission.v1alpha1","files":{}})

      for _attempt <- 1..12 do
        Phoenix.ConnTest.build_conn() |> Map.put(:remote_ip, flooder) |> publish(body)
      end

      assert conn
             |> from_own_address()
             |> publish(NetworkFixture.submission())
             |> Map.fetch!(:status) ==
               201
    end
  end

  describe "reading a published run back" do
    test "the exact bytes come back, with an entity tag that is their digest", %{conn: conn} do
      submission = NetworkFixture.submission()
      publish(conn, submission)

      served = get(build_conn(), "/api/v1/submissions/#{NetworkFixture.bundle_digest()}")

      assert served.status == 200
      assert served.resp_body == submission

      assert get_resp_header(served, "etag") ==
               [~s("#{Techtree.Catalog.Digest.hash_bytes(submission)}")]

      assert get_resp_header(served, "cache-control") ==
               ["public, max-age=31536000, immutable"]
    end

    test "a caller who already holds those bytes is told so", %{conn: conn} do
      submission = NetworkFixture.submission()
      publish(conn, submission)

      etag = ~s("#{Techtree.Catalog.Digest.hash_bytes(submission)}")

      served =
        build_conn()
        |> put_req_header("if-none-match", etag)
        |> get("/api/v1/submissions/#{NetworkFixture.bundle_digest()}")

      assert served.status == 304
      assert served.resp_body == ""
    end

    test "a fingerprint nothing is published under is a 404" do
      served =
        get(build_conn(), "/api/v1/submissions/sha256:#{String.duplicate("a", 64)}")

      assert served.status == 404
      assert %{"error" => %{"code" => "submission_missing"}} = json_response(served, 404)
    end

    test "a withdrawn entry is gone rather than missing", %{conn: conn} do
      publish(conn, NetworkFixture.submission())

      {:ok, entry} = Techtree.Network.Query.get_entry(NetworkFixture.bundle_digest())
      Ingest.withdraw(entry, :requested_by_publisher)

      served = get(build_conn(), "/api/v1/submissions/#{NetworkFixture.bundle_digest()}")

      assert served.status == 410
      assert %{"error" => %{"code" => "submission_withdrawn"}} = json_response(served, 410)
    end
  end

  describe "an address a publisher volunteers" do
    test "is taken from beside the body and never appears anywhere public", %{conn: conn} do
      conn =
        conn
        |> put_req_header("x-techtree-contributor-address", @address)
        |> publish(NetworkFixture.submission())

      assert conn.status == 201
      refute conn.resp_body =~ "0x"

      assert Ingest.contributor_address(String.downcase(@address)).submission_count == 1

      served = get(build_conn(), "/api/v1/submissions/#{NetworkFixture.bundle_digest()}")

      refute served.resp_body =~ @address
      refute served.resp_body =~ String.downcase(@address)
      assert served.resp_body == NetworkFixture.submission()
    end

    test "with a character wrong takes the whole publication down with it", %{conn: conn} do
      conn =
        conn
        |> put_req_header(
          "x-techtree-contributor-address",
          "0x5aAeb6053f3E94C9b9A09f33669435E7Ef1BeAed"
        )
        |> publish(NetworkFixture.submission())

      assert conn.status == 422
      assert %{"error" => %{"code" => "contributor_address_invalid"}} = json_response(conn, 422)
      assert Network.list_submissions!() == []
    end
  end

  defp publish(conn, body) do
    conn
    |> put_req_header("content-type", "application/json")
    |> post("/api/v1/submissions", body)
  end

  defp from_own_address(conn), do: Map.put(conn, :remote_ip, own_address())

  # One address per test, so that the rate limiter — which is real, shared and
  # counted per caller — cannot make one test the continuation of another.
  defp own_address do
    number = System.unique_integer([:positive])

    {198, 51, rem(div(number, 254), 254) + 1, rem(number, 254) + 1}
  end
end
