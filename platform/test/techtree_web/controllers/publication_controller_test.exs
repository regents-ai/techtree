defmodule TechtreeWeb.PublicationControllerTest do
  @moduledoc """
  The one address that accepts anything, and the addresses that read the log
  back, exercised the way a caller would.

  Two documents arrive at that one address — a finished run somebody is
  publishing, and a signed request to withdraw one they published — so the
  tests send both to the same place and vary only what is in the body. Both
  receipts are signed envelopes, checked here the way anybody holding one would
  check it: canonicalize the payload, hash it, compare it to `payload_digest`,
  and verify the signature over that digest string.

  The limits are tested by exceeding them rather than by reading the numbers
  back out of the configuration, because a test that asks the code what its own
  limit is agrees with the code no matter what the limit does. The one number
  read back is the body cap itself, which the founder fixed at two mebibytes:
  that assertion is about the configuration file rather than about the code
  that reads it.

  Each test speaks from its own address. The rate limiter counts per caller and
  the counting is real, so tests that all claimed to be the same caller would be
  each other's second attempt.
  """

  use TechtreeWeb.ConnCase, async: false

  import ExUnit.CaptureLog

  alias Techtree.Canonical
  alias Techtree.Catalog.Digest
  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture
  alias Techtree.Network
  alias Techtree.Network.Bundle
  alias Techtree.Network.Ingest
  alias Techtree.Network.Key
  alias Techtree.Network.Query
  alias Techtree.NetworkFixture
  alias TechtreeWeb.Endpoint

  @address "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"

  setup %{conn: conn} do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())

    {:ok, conn: from_own_address(conn)}
  end

  describe "publishing a run" do
    test "a real bundle is accepted, and the receipt is the envelope 0038 fixes",
         %{conn: conn} do
      conn = publish(conn, NetworkFixture.submission())

      assert conn.status == 201

      body = json_response(conn, 201)

      assert Enum.sort(Map.keys(body)) == ["payload", "payload_digest", "signature"]

      payload = body["payload"]

      assert Enum.sort(Map.keys(payload)) == [
               "accepted_at",
               "bundle_digest",
               "checks",
               "entry_url",
               "id",
               "log_sequence",
               "public_key",
               "run_id",
               "schema_version"
             ]

      assert payload["schema_version"] == "techtree.publication-receipt.v1alpha1"
      assert payload["bundle_digest"] == NetworkFixture.bundle_digest()
      assert payload["run_id"] == NetworkFixture.report()["payload"]["run_id"]
      assert payload["log_sequence"] >= 1

      assert payload["entry_url"] ==
               Endpoint.url() <> "/results/" <> NetworkFixture.bundle_digest()

      assert get_resp_header(conn, "location") ==
               ["/api/v1/publications/#{NetworkFixture.bundle_digest()}"]
    end

    test "the payload digest is the digest of the payload and of nothing else",
         %{conn: conn} do
      body = conn |> publish(NetworkFixture.submission()) |> json_response(201)

      assert body["payload_digest"] ==
               body["payload"] |> Canonical.encode!() |> Digest.hash_bytes()
    end

    test "the receipt names every check the ingest actually ran", %{conn: conn} do
      body = conn |> publish(NetworkFixture.submission()) |> json_response(201)

      expected =
        Enum.map(Bundle.checks(), fn {id, detail} ->
          %{"id" => to_string(id), "passed" => true, "detail" => detail}
        end)

      assert body["payload"]["checks"] == expected
      assert length(body["payload"]["checks"]) == Bundle.check_count()
    end

    test "the receipt says when the log accepted it, in UTC", %{conn: conn} do
      accepted = conn |> publish(NetworkFixture.submission()) |> json_response(201)
      said = accepted["payload"]["accepted_at"]

      assert {:ok, accepted_at, 0} = DateTime.from_iso8601(said)
      assert String.ends_with?(said, "Z")
      assert DateTime.diff(DateTime.utc_now(), accepted_at, :second) < 60
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
      assert Network.list_publication_entries!() == []
    end

    test "a body that is not sent as JSON is refused before anything is read", %{conn: conn} do
      conn =
        conn
        |> put_req_header("content-type", "application/octet-stream")
        |> post("/api/v1/publications", NetworkFixture.submission())

      assert conn.status == 400
      assert %{"error" => %{"code" => "submission_malformed"}} = json_response(conn, 400)
      assert Network.list_publication_entries!() == []
    end
  end

  describe "the body cap" do
    test "is the two mebibytes the founder fixed" do
      assert Network.maximum_body_bytes() == 2 * 1024 * 1024
    end

    test "a body over it is refused at the parser, before it is decoded", %{conn: conn} do
      oversized =
        Jason.encode!(%{
          "schema_version" => "techtree.publication-submission.v1alpha1",
          "run_id" => "run_c4758ddb5bba4023aa3530b47f4582e9",
          "bundle_digest" => NetworkFixture.bundle_digest(),
          "files" => %{"bundle.json" => String.duplicate("a", 3_000_000)}
        })

      refused =
        assert_raise Plug.Parsers.RequestTooLargeError, fn ->
          publish(conn, oversized)
        end

      assert Plug.Exception.status(refused) == 413
      assert Network.list_publication_entries!() == []
    end

    test "a body under it reaches the checks", %{conn: conn} do
      assert publish(conn, NetworkFixture.submission()).status == 201
    end
  end

  describe "the rate limit" do
    test "one caller sending run after run is asked to wait" do
      caller = own_address()
      body = ~s({"schema_version":"techtree.publication-submission.v1alpha1","files":{}})

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
      body = ~s({"schema_version":"techtree.publication-submission.v1alpha1","files":{}})

      refused =
        Enum.reduce(1..12, nil, fn _attempt, _previous ->
          Phoenix.ConnTest.build_conn()
          |> Map.put(:remote_ip, caller)
          |> publish(body)
        end)

      assert refused.status == 429

      assert %{"error" => %{"code" => "publication_rate_limited", "retryable" => true}} =
               json_response(refused, 429)

      assert [seconds] = get_resp_header(refused, "retry-after")
      assert String.to_integer(seconds) > 0
    end

    test "another caller is unaffected by the first one's flood", %{conn: conn} do
      flooder = own_address()
      body = ~s({"schema_version":"techtree.publication-submission.v1alpha1","files":{}})

      for _attempt <- 1..12 do
        Phoenix.ConnTest.build_conn() |> Map.put(:remote_ip, flooder) |> publish(body)
      end

      assert conn
             |> from_own_address()
             |> publish(NetworkFixture.submission())
             |> Map.fetch!(:status) == 201
    end
  end

  describe "idempotence over the wire" do
    test "the first publication is 201 and the same one again is 200", %{conn: conn} do
      first = publish(conn, NetworkFixture.submission())

      assert first.status == 201

      again =
        conn |> recycle() |> from_own_address() |> publish(NetworkFixture.submission())

      assert again.status == 200

      # Not merely equivalent: the identical bytes, which is what "the original
      # receipt" has to mean for a participant writing one into a run directory.
      assert again.resp_body == first.resp_body
      assert length(Network.list_publication_entries!()) == 1
    end

    test "the same digest already held under different bytes is 409", %{conn: conn} do
      NetworkFixture.seed_entry(submission_digest: "sha256:" <> String.duplicate("0", 64))

      refused = publish(conn, NetworkFixture.submission())

      assert refused.status == 409

      assert %{"error" => %{"code" => "publication_bytes_conflict"}} =
               json_response(refused, 409)
    end

    test "the same participant and run under a different bundle is 409", %{conn: conn} do
      keys = NetworkFixture.key_pair()
      first = NetworkFixture.resign(NetworkFixture.files(), keys: keys)

      assert publish(conn, NetworkFixture.submission(first)).status == 201

      second =
        first
        |> Map.update!("receipts/baseline/0000.json", fn bytes ->
          bytes
          |> Jason.decode!()
          |> update_in(["payload"], &Map.put(&1, "score_status", "valid "))
          |> Jason.encode!()
        end)
        |> NetworkFixture.resign(keys: keys)

      refused =
        conn |> recycle() |> from_own_address() |> publish(NetworkFixture.submission(second))

      assert refused.status == 409
      assert %{"error" => %{"code" => "publication_run_conflict"}} = json_response(refused, 409)
      assert length(Network.list_publication_entries!()) == 1
    end

    test "an idempotency key is neither required nor read", %{conn: conn} do
      first =
        conn
        |> put_req_header("idempotency-key", "one")
        |> publish(NetworkFixture.submission())

      assert first.status == 201

      # A different key on the same proof is still the same publication: the
      # digest of the bundle is what makes it one, not a header somebody chose.
      again =
        conn
        |> recycle()
        |> from_own_address()
        |> put_req_header("idempotency-key", "two")
        |> publish(NetworkFixture.submission())

      assert again.status == 200
      assert again.resp_body == first.resp_body
    end
  end

  describe "reading the log" do
    setup %{conn: conn} do
      publish(conn, NetworkFixture.submission())
      :ok
    end

    test "the list is a verified projection and never the submitted bytes" do
      served = get(build_conn(), "/api/v1/publications")

      assert served.status == 200

      body = json_response(served, 200)

      assert body["schema_version"] == "techtree.publication-log.v1alpha1"
      assert [entry] = body["entries"]
      assert entry["log_sequence"] >= 1
      assert entry["bundle_digest"] == NetworkFixture.bundle_digest()
      assert entry["entry_url"] == Endpoint.url() <> "/results/" <> NetworkFixture.bundle_digest()
      assert entry["subject"]["provider"] == "prime"
      assert entry["result"]["wins"] == 23
      assert entry["checks"] == %{"run" => Bundle.check_count(), "passed" => Bundle.check_count()}
      assert is_nil(entry["withdrawn_at"])

      refute served.resp_body =~ "files"
      refute served.resp_body =~ Base.encode64(NetworkFixture.files()["data-policy.json"])
    end

    test "the detail adds the tasks and the receipt it issued, and no bytes" do
      served = get(build_conn(), "/api/v1/publications/#{NetworkFixture.bundle_digest()}")

      assert served.status == 200

      body = json_response(served, 200)

      assert body["schema_version"] == "techtree.publication-entry.v1alpha1"
      assert length(body["task_deltas"]) == 36
      assert body["receipt"]["key_id"] == elem(Key.load(), 1).key_id
      assert Digest.valid?(body["receipt"]["payload_digest"])

      refute served.resp_body =~ Base.encode64(NetworkFixture.files()["data-policy.json"])
    end

    test "a fingerprint nothing is published under is a 404" do
      served = get(build_conn(), "/api/v1/publications/sha256:#{String.duplicate("a", 64)}")

      assert served.status == 404
      assert %{"error" => %{"code" => "publication_missing"}} = json_response(served, 404)
    end

    test "there is no address that returns the bytes that were submitted" do
      for path <- [
            "/api/v1/submissions/#{NetworkFixture.bundle_digest()}",
            "/api/v1/publications/#{NetworkFixture.bundle_digest()}/bundle",
            "/api/v1/bundles/#{NetworkFixture.bundle_digest()}"
          ] do
        assert get(build_conn(), path).status == 404
      end
    end
  end

  describe "reading the log a page at a time" do
    setup %{conn: conn} do
      entries =
        for dropped <- [0, 1, 2, 3] do
          {:ok, entry, :recorded} =
            NetworkFixture.publish(NetworkFixture.submission(shortened_by(dropped)))

          entry
        end

      {:ok, conn: conn, entries: entries}
    end

    test "is newest first by log sequence and by nothing else", %{entries: entries} do
      body = build_conn() |> get("/api/v1/publications") |> json_response(200)

      assert Enum.map(body["entries"], & &1["log_sequence"]) ==
               entries |> Enum.map(& &1.log_sequence) |> Enum.sort(:desc)
    end

    test "takes a keyset and a limit, and says where the next page starts", %{entries: entries} do
      newest = entries |> Enum.map(& &1.log_sequence) |> Enum.max()

      first = build_conn() |> get("/api/v1/publications?limit=2") |> json_response(200)

      assert length(first["entries"]) == 2
      assert hd(first["entries"])["log_sequence"] == newest
      assert first["next_before_sequence"] == List.last(first["entries"])["log_sequence"]

      next =
        build_conn()
        |> get("/api/v1/publications?limit=2&before_sequence=#{first["next_before_sequence"]}")
        |> json_response(200)

      assert length(next["entries"]) == 2
      assert next["next_before_sequence"] == nil

      assert Enum.all?(
               next["entries"],
               &(&1["log_sequence"] < first["next_before_sequence"])
             )
    end

    test "defaults to twenty-five and refuses more than a hundred" do
      assert Network.default_page_size() == 25
      assert Network.maximum_page_size() == 100

      over = build_conn() |> get("/api/v1/publications?limit=101")

      assert over.status == 400

      assert %{"error" => %{"code" => "publication_query_invalid", "message" => message}} =
               json_response(over, 400)

      assert message =~ "at most 100"
    end

    test "refuses a keyset that is not a log sequence" do
      for query <- ["before_sequence=soon", "before_sequence=-1", "limit=0", "limit=many"] do
        refused = get(build_conn(), "/api/v1/publications?" <> query)

        assert refused.status == 400, "#{query} was not refused"
      end
    end

    # Four bundles of the same run under four keys, each one task shorter than
    # the campaign committed to would be — so instead the reward of the first
    # `dropped` tasks is flattened, which keeps the membership intact.
    defp shortened_by(dropped) do
      NetworkFixture.files()
      |> Map.update!("uplift-report.json", fn bytes ->
        bytes
        |> Jason.decode!()
        |> update_in(["payload", "task_deltas"], fn deltas ->
          deltas
          |> Enum.with_index()
          |> Enum.map(fn {delta, index} ->
            if index < dropped, do: Map.put(delta, "candidate_reward", 0), else: delta
          end)
        end)
        |> tally()
        |> Jason.encode!()
      end)
      |> NetworkFixture.resign()
    end

    defp tally(envelope) do
      counted =
        Enum.frequencies_by(envelope["payload"]["task_deltas"], fn delta ->
          cond do
            delta["candidate_reward"] > delta["baseline_reward"] -> "wins"
            delta["candidate_reward"] < delta["baseline_reward"] -> "losses"
            true -> "ties"
          end
        end)

      update_in(envelope, ["payload", "primary_result"], fn result ->
        Enum.reduce(["wins", "losses", "ties"], result, fn outcome, acc ->
          Map.put(acc, outcome, Map.get(counted, outcome, 0))
        end)
      end)
    end
  end

  describe "withdrawing a run at the same address" do
    setup %{conn: conn} do
      keys = NetworkFixture.key_pair()
      files = NetworkFixture.resign(NetworkFixture.files(), keys: keys)

      {:ok, entry, :recorded} = NetworkFixture.publish(NetworkFixture.submission(files))

      {:ok, conn: conn, entry: entry, keys: keys}
    end

    test "the publisher's own signed request is answered with its own receipt", context do
      %{conn: conn, entry: entry, keys: keys} = context

      conn = publish(conn, NetworkFixture.withdrawal(entry.bundle_digest, keys))

      assert conn.status == 200

      body = json_response(conn, 200)

      assert Enum.sort(Map.keys(body)) == ["payload", "payload_digest", "signature"]

      payload = body["payload"]

      assert Enum.sort(Map.keys(payload)) == [
               "bundle_digest",
               "entry_url",
               "public_key",
               "schema_version",
               "withdrawn_at"
             ]

      assert payload["schema_version"] == "techtree.publication-withdrawal-receipt.v1alpha1"
      assert payload["bundle_digest"] == entry.bundle_digest
      assert payload["entry_url"] == Endpoint.url() <> "/results/" <> entry.bundle_digest
      assert {:ok, _at, 0} = DateTime.from_iso8601(payload["withdrawn_at"])
      assert String.ends_with?(payload["withdrawn_at"], "Z")

      assert body["payload_digest"] == payload |> Canonical.encode!() |> Digest.hash_bytes()
      assert verified?(body)
    end

    test "the entry stays on the log, marked, and keeps everything it published", context do
      %{conn: conn, entry: entry, keys: keys} = context

      publish(conn, NetworkFixture.withdrawal(entry.bundle_digest, keys))

      listed = build_conn() |> get("/api/v1/publications") |> json_response(200)

      assert [shown] = listed["entries"]
      assert shown["bundle_digest"] == entry.bundle_digest
      refute is_nil(shown["withdrawn_at"])
      assert shown["result"]["wins"] == entry.wins

      page = get(build_conn(), "/results/#{entry.bundle_digest}")

      assert page.status == 200
      assert page.resp_body =~ "Withdrawn by the participant"
    end

    test "somebody else's signature is refused and changes nothing", context do
      %{conn: conn, entry: entry} = context

      conn =
        publish(
          conn,
          NetworkFixture.withdrawal(entry.bundle_digest, NetworkFixture.key_pair())
        )

      assert conn.status == 422
      assert %{"error" => %{"code" => "withdrawal_signature_invalid"}} = json_response(conn, 422)

      assert {:ok, held} = Query.get_entry(entry.bundle_digest)
      assert is_nil(held.withdrawn_at)
    end

    test "a request naming a run this log does not hold is a 404", context do
      %{conn: conn, keys: keys} = context

      absent = "sha256:" <> String.duplicate("3", 64)
      conn = publish(conn, NetworkFixture.withdrawal(absent, keys))

      assert conn.status == 404
      assert %{"error" => %{"code" => "withdrawal_entry_missing"}} = json_response(conn, 404)
    end

    test "a fourth member in the payload is refused", context do
      %{conn: conn, entry: entry, keys: keys} = context

      payload = %{
        "schema_version" => "techtree.publication-withdrawal.v1alpha1",
        "bundle_digest" => entry.bundle_digest,
        "requested_at" => DateTime.to_iso8601(DateTime.utc_now()),
        "reason" => "changed my mind"
      }

      conn =
        publish(conn, NetworkFixture.withdrawal(entry.bundle_digest, keys, payload: payload))

      assert conn.status == 400
      assert %{"error" => %{"code" => "withdrawal_malformed"}} = json_response(conn, 400)
    end

    test "a body that is neither document names both of them", %{conn: conn} do
      conn = publish(conn, ~s({"schema_version":"techtree.something-else.v1alpha1"}))

      assert conn.status == 400

      assert %{"error" => %{"code" => "submission_malformed", "message" => message}} =
               json_response(conn, 400)

      assert message =~ "publication-submission"
      assert message =~ "publication-withdrawal"
    end

    test "sent twice appends one event and answers the same way", context do
      %{conn: conn, entry: entry, keys: keys} = context

      first = publish(conn, NetworkFixture.withdrawal(entry.bundle_digest, keys))

      again =
        conn
        |> recycle()
        |> from_own_address()
        |> publish(NetworkFixture.withdrawal(entry.bundle_digest, keys))

      assert first.status == 200
      assert again.status == 200
      assert again.resp_body == first.resp_body

      assert Enum.count(Network.list_publication_events!(), &(&1.kind == :withdrawn)) == 1
    end
  end

  describe "an address a publisher volunteers" do
    test "is taken from beside the body and never appears anywhere public", %{conn: conn} do
      conn =
        conn
        |> put_req_header("x-techtree-contributor-address", @address)
        |> publish(NetworkFixture.submission())

      assert conn.status == 201
      refute conn.resp_body =~ @address
      refute conn.resp_body =~ String.downcase(@address)

      assert [record] = Ingest.contributor_address(@address)
      assert record.contributor_address_unverified == String.downcase(@address)

      for path <- [
            "/api/v1/publications",
            "/api/v1/publications/#{NetworkFixture.bundle_digest()}",
            "/results",
            "/results/#{NetworkFixture.bundle_digest()}"
          ] do
        served = get(build_conn(), path)

        refute served.resp_body =~ @address
        refute served.resp_body =~ String.downcase(@address)
      end
    end

    test "with a character wrong takes the whole publication down with it", %{conn: conn} do
      damaged = "0x5aAeb6053f3E94C9b9A09f33669435E7Ef1BeAed"

      conn =
        conn
        |> put_req_header("x-techtree-contributor-address", damaged)
        |> publish(NetworkFixture.submission())

      assert conn.status == 422
      assert %{"error" => %{"code" => "contributor_address_invalid"}} = json_response(conn, 422)
      assert Network.list_publication_entries!() == []

      # A refusal that quoted the address back would put it in the one place
      # this whole design keeps it out of, and would do it while telling
      # somebody their address was wrong.
      refute conn.resp_body =~ damaged
      refute conn.resp_body =~ String.downcase(damaged)
    end

    test "is never written into a log line, published or refused", %{conn: conn} do
      logged =
        capture_log([level: :debug], fn ->
          conn
          |> put_req_header("x-techtree-contributor-address", @address)
          |> publish(NetworkFixture.submission())

          build_conn()
          |> from_own_address()
          |> put_req_header(
            "x-techtree-contributor-address",
            "0x5aAeb6053f3E94C9b9A09f33669435E7Ef1BeAed"
          )
          |> publish(NetworkFixture.submission())
        end)

      refute logged =~ @address
      refute logged =~ String.downcase(@address)
    end

    # What a telemetry reporter would actually export is a metric's measurement
    # and the tags that metric declares, so that is what is checked rather than
    # the raw metadata: a request's own headers are on the `conn` an event
    # carries whether anybody wants them or not, and the question worth asking
    # is whether any of that becomes a dimension this build reports. A metric
    # that grew a tag drawn from the request would fail this.
    test "is in no dimension of any metric this build reports", %{conn: conn} do
      metrics = TechtreeWeb.Telemetry.metrics()
      collector = self()

      handlers =
        metrics
        |> Enum.map(& &1.event_name)
        |> Enum.uniq()
        |> Enum.map(fn event ->
          id = {__MODULE__, event, make_ref()}

          :telemetry.attach(
            id,
            event,
            fn name, measurements, metadata, _config ->
              send(collector, {:reported, name, measurements, metadata})
            end,
            nil
          )

          id
        end)

      on_exit(fn -> Enum.each(handlers, &:telemetry.detach/1) end)

      conn
      |> put_req_header("x-techtree-contributor-address", @address)
      |> publish(NetworkFixture.submission())

      exported = exported_dimensions(metrics)

      # A test that reported nothing would pass for the wrong reason.
      refute exported == ""

      refute exported =~ @address
      refute exported =~ String.downcase(@address)
    end
  end

  describe "the countersignature" do
    test "verifies against the key served at the fingerprint it names", %{conn: conn} do
      receipt = conn |> publish(NetworkFixture.submission()) |> json_response(201)

      published =
        build_conn()
        |> get("/api/v1/publication-keys/#{receipt["payload"]["public_key"]["key_id"]}")
        |> json_response(200)

      assert receipt["payload"]["public_key"] == published
      assert receipt["signature"]["key_id"] == published["key_id"]
      assert receipt["signature"]["algorithm"] == "ed25519"
      assert verified?(receipt)
    end

    test "is over every member of the payload, and the payload alone", %{conn: conn} do
      receipt = conn |> publish(NetworkFixture.submission()) |> json_response(201)

      for member <- Map.keys(receipt["payload"]) do
        tampered = put_in(receipt, ["payload", member], "tampered")

        refute verified?(tampered), "changing #{member} left the receipt verifying"
      end
    end

    test "does not verify under a key that is not the one that made it", %{conn: conn} do
      receipt = conn |> publish(NetworkFixture.submission()) |> json_response(201)

      {other, _private} = :crypto.generate_key(:eddsa, :ed25519)

      refute verify(receipt, other)
    end

    test "the fingerprint the receipt names is the hash of the key it names", %{conn: conn} do
      receipt = conn |> publish(NetworkFixture.submission()) |> json_response(201)
      key = receipt["payload"]["public_key"]

      assert key["key_id"] == Digest.hash_bytes(Base.decode64!(key["public_key"]))
    end
  end

  describe "the published public key" do
    test "is served at its own fingerprint, as the three-member document" do
      {:ok, key} = Key.load()

      served = get(build_conn(), "/api/v1/publication-keys/#{key.key_id}")

      assert served.status == 200
      assert Enum.sort(Map.keys(json_response(served, 200))) == ~w(algorithm key_id public_key)
      assert get_resp_header(served, "etag") == [~s("#{Digest.hash_bytes(served.resp_body)}")]

      assert json_response(served, 200)["key_id"] ==
               Digest.hash_bytes(Base.decode64!(json_response(served, 200)["public_key"]))
    end

    test "is not served at a fingerprint this build holds no key for" do
      served = get(build_conn(), "/api/v1/publication-keys/sha256:#{String.duplicate("a", 64)}")

      assert served.status == 404
      assert %{"error" => %{"code" => "network_key_missing"}} = json_response(served, 404)
    end

    test "is not served at all by a build that holds no key" do
      {:ok, key} = Key.load()

      without_a_key(fn ->
        served = get(build_conn(), "/api/v1/publication-keys/#{key.key_id}")

        assert served.status == 503

        assert %{"error" => %{"code" => "network_key_unavailable", "retryable" => true}} =
                 json_response(served, 503)
      end)
    end
  end

  describe "a build that holds no signing key" do
    test "publishes nothing, and says so rather than accepting silently", %{conn: conn} do
      without_a_key(fn ->
        refused = publish(conn, NetworkFixture.submission())

        assert refused.status == 503

        assert %{"error" => %{"code" => "network_key_unavailable", "retryable" => true}} =
                 json_response(refused, 503)

        assert Network.list_publication_entries!() == []
      end)
    end

    test "accepts the identical bundle once a key is there", %{conn: conn} do
      without_a_key(fn -> assert publish(conn, NetworkFixture.submission()).status == 503 end)

      assert conn
             |> recycle()
             |> from_own_address()
             |> publish(NetworkFixture.submission())
             |> Map.fetch!(:status) == 201
    end
  end

  # Everything the reporters attached to these metrics would put on the wire:
  # each metric's measurement, and the values of the tags it declares.
  defp exported_dimensions(metrics) do
    receive do
      {:reported, name, measurements, metadata} ->
        dimensions =
          metrics
          |> Enum.filter(&(&1.event_name == name))
          |> Enum.map(fn metric ->
            {Map.get(measurements, metric.measurement),
             metadata |> metric.tag_values.() |> Map.take(metric.tags)}
          end)

        inspect(dimensions) <> exported_dimensions(metrics)
    after
      0 -> ""
    end
  end

  defp publish(conn, body) do
    conn
    |> put_req_header("content-type", "application/json")
    |> post("/api/v1/publications", body)
  end

  # The whole of the check anybody holding one of these would run: canonicalize
  # the payload, hash it, require the envelope to have written that same digest
  # down, and verify the signature over that digest string. Recomputed here
  # rather than asked of the code that made it.
  defp verified?(receipt) do
    {:ok, key} = Key.load()

    verify(receipt, key.public)
  end

  defp verify(receipt, public) do
    digest = receipt["payload"] |> Canonical.encode!() |> Digest.hash_bytes()

    digest == receipt["payload_digest"] and
      :crypto.verify(
        :eddsa,
        :none,
        digest,
        Base.decode64!(receipt["signature"]["signature"]),
        [public, :ed25519]
      )
  end

  defp without_a_key(body) do
    configured = Application.get_env(:techtree, Key)
    Application.delete_env(:techtree, Key)

    try do
      body.()
    after
      Application.put_env(:techtree, Key, configured)
    end
  end

  defp from_own_address(conn), do: Map.put(conn, :remote_ip, own_address())

  # One address per test, so that the rate limiter — which is real, shared and
  # counted per caller — cannot make one test the continuation of another.
  defp own_address do
    number = System.unique_integer([:positive])

    {198, 51, rem(div(number, 254), 254) + 1, rem(number, 254) + 1}
  end
end
