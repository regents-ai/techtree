defmodule TechtreeWeb.PublicationBundleControllerTest do
  @moduledoc """
  The address that hands back what a participant submitted, exactly.

  The whole point of this address is that nothing happened to the bytes on the
  way through, so the tests compare the response to the string that was posted
  rather than to a document assembled here. One of them posts a submission
  written out with indentation, which no encoder on this site would produce: if
  the answer came back canonical, or came back with the whitespace gone, the
  site would have re-rendered somebody else's signed document and the check
  a reader runs offline would be checking our rendering instead of their run.

  Withdrawal is tested for what it leaves behind as much as for what it stops.
  The download goes to `410`, and the entry, the appended event and the receipt
  are all still readable — a `404` here would be this site claiming a run it
  published and countersigned had never arrived.
  """

  use TechtreeWeb.ConnCase, async: false

  alias Techtree.Catalog.Digest
  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture
  alias Techtree.Network
  alias Techtree.NetworkFixture

  setup do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())
    :ok
  end

  describe "downloading a published run" do
    test "answers with the exact bytes that were posted", %{conn: conn} do
      submitted = NetworkFixture.submission()

      posted =
        conn
        |> from_own_address()
        |> put_req_header("content-type", "application/json")
        |> post("/api/v1/publications", submitted)

      assert posted.status == 201

      served = get(build_conn(), bundle_path(NetworkFixture.bundle_digest()))

      assert served.status == 200
      assert served.resp_body == submitted
    end

    test "does not re-encode a submission written out with whitespace", %{conn: conn} do
      indented = NetworkFixture.submission() |> Jason.decode!() |> Jason.encode!(pretty: true)

      # A guard on the fixture rather than on the code: if this ever stopped
      # differing from what an encoder here produces, the test below would pass
      # for the wrong reason.
      assert String.contains?(indented, "\n")
      refute indented == NetworkFixture.submission()

      {:ok, entry, :recorded} = NetworkFixture.publish(indented)

      served = get(conn, bundle_path(entry.bundle_digest))

      assert served.status == 200
      assert served.resp_body == indented
    end

    test "is not stored by anything between here and the reader", %{conn: conn} do
      {:ok, entry, :recorded} = NetworkFixture.publish()

      served = get(conn, bundle_path(entry.bundle_digest))

      assert get_resp_header(served, "cache-control") == ["no-store"]
      assert get_resp_header(served, "content-type") == ["application/json"]
      assert get_resp_header(served, "etag") == [~s("#{Digest.hash_bytes(served.resp_body)}")]
    end

    test "a fingerprint nothing was published under is a 404", %{conn: conn} do
      served = get(conn, bundle_path("sha256:" <> String.duplicate("a", 64)))

      assert served.status == 404
      assert %{"error" => %{"code" => "publication_missing"}} = json_response(served, 404)
    end

    test "a path that is not a fingerprint at all is a 400", %{conn: conn} do
      served = get(conn, bundle_path("not-a-digest"))

      assert served.status == 400

      assert %{"error" => %{"code" => "publication_digest_invalid", "retryable" => false}} =
               json_response(served, 400)
    end
  end

  describe "downloading a run the participant withdrew" do
    setup %{conn: conn} do
      keys = NetworkFixture.key_pair()
      files = NetworkFixture.resign(NetworkFixture.files(), keys: keys)

      {:ok, entry, :recorded} = NetworkFixture.publish(NetworkFixture.submission(files))

      conn
      |> from_own_address()
      |> put_req_header("content-type", "application/json")
      |> post("/api/v1/publications", NetworkFixture.withdrawal(entry.bundle_digest, keys))
      |> then(&assert(&1.status == 200))

      {:ok, entry: entry}
    end

    test "is gone rather than missing", %{conn: conn, entry: entry} do
      served = get(conn, bundle_path(entry.bundle_digest))

      assert served.status == 410

      assert %{"error" => %{"code" => "publication_withdrawn", "retryable" => false}} =
               json_response(served, 410)
    end

    test "leaves the metadata, the tombstone and the receipt where they were", context do
      %{conn: conn, entry: entry} = context

      shown = conn |> get("/api/v1/publications/#{entry.bundle_digest}") |> json_response(200)

      assert shown["bundle_digest"] == entry.bundle_digest
      assert shown["log_sequence"] == entry.log_sequence
      refute is_nil(shown["withdrawn_at"])
      assert shown["receipt"]["payload_digest"] == entry.receipt_digest

      kinds =
        Network.list_publication_events!()
        |> Enum.filter(&(&1.publication_entry_id == entry.id))
        |> Enum.map(& &1.kind)

      assert :accepted in kinds
      assert :withdrawn in kinds

      {:ok, held} = Network.get_publication_entry_by_digest(entry.bundle_digest)

      assert held.submission_bytes == entry.submission_bytes
      assert held.receipt_bytes == entry.receipt_bytes
    end
  end

  defp bundle_path(digest), do: "/api/v1/publications/#{digest}/bundle"

  defp from_own_address(conn), do: Map.put(conn, :remote_ip, own_address())

  # One address per test: the rate limiter is real and counts per caller, so a
  # shared one would make one test the continuation of another.
  defp own_address do
    number = System.unique_integer([:positive])

    {198, 51, rem(div(number, 254), 254) + 1, rem(number, 254) + 1}
  end
end
