defmodule Techtree.Network.IngestTest do
  @moduledoc """
  A submission becomes a row only if every check holds, and each check has to
  be shown refusing on its own.

  The honest bundle here is a real one — a finished run copied off the machine
  that produced it, signatures and all — so "it accepts a good bundle" is a
  claim about a bundle this repository did not make. Every refusal is that same
  bundle with exactly one thing wrong with it.

  Reaching the checks at the far end takes some care. A bundle whose numbers
  were edited fails the signature check long before anything reads the numbers,
  so the tests for the later checks hand over a bundle that is perfectly signed
  under a key made for the occasion and simply wrong about what it claims. That
  is the case worth refusing: not a bundle somebody broke, but one somebody
  built.
  """

  use Techtree.DataCase, async: false

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture
  alias Techtree.Network
  alias Techtree.Network.Bundle
  alias Techtree.Network.Ingest
  alias Techtree.NetworkFixture

  @report_path "uplift-report.json"
  @manifest_path "bundle.json"
  @policy_path "data-policy.json"

  describe "with nothing published to anchor a run to" do
    test "an honest bundle is refused, because the campaign it names is not ours" do
      assert {:error, %{code: :submission_campaign_unpublished}} = NetworkFixture.publish()

      assert Network.list_publication_entries!() == []
    end
  end

  describe "a real proof bundle" do
    setup :publish_the_catalog

    test "is accepted, and every published field is recomputed rather than copied" do
      assert {:ok, entry, :recorded} = NetworkFixture.publish()

      report = NetworkFixture.report()["payload"]
      manifest = NetworkFixture.manifest()["payload"]

      assert entry.log_sequence >= 1
      assert entry.bundle_digest == NetworkFixture.bundle_digest()
      assert entry.run_id == manifest["run_id"]
      assert entry.campaign_spec_digest == manifest["campaign_spec_digest"]
      assert entry.data_policy_digest == manifest["data_policy_digest"]
      assert entry.climb_reference == CatalogFixture.climb_reference()
      assert entry.participant_kind == :local_ed25519
      assert entry.participant_key_id == manifest["executor_identity"]["key_id"]
      assert entry.participant_public_key == manifest["executor_identity"]["public_key"]
      assert entry.subject_harness == "hermes-agent"
      assert entry.subject_harness_version == "0.19.0"
      assert entry.subject_model == "qwen/qwen3.7-flash"
      assert entry.subject_provider == "prime"
      assert entry.wins == report["primary_result"]["wins"]
      assert entry.losses == report["primary_result"]["losses"]
      assert entry.ties == report["primary_result"]["ties"]
      assert entry.task_count == 36
      assert length(entry.task_deltas) == 36
      assert entry.statuses == report["statuses"]
      assert entry.decision == "accepted"
      assert entry.proof_grade == "P1"
      assert entry.verification_checks_run == Bundle.check_count()
      assert entry.verification_checks_passed == Bundle.check_count()
      assert entry.submission_bytes == NetworkFixture.submission()
      assert is_nil(entry.withdrawn_at)
    end

    test "is stored whole, with the receipt it was issued written in the same row" do
      assert {:ok, entry, :recorded} = NetworkFixture.publish()

      receipt = Jason.decode!(entry.receipt_bytes)
      payload = receipt["payload"]

      assert payload["schema_version"] == "techtree.publication-receipt.v1alpha1"
      assert payload["log_sequence"] == entry.log_sequence
      assert payload["bundle_digest"] == entry.bundle_digest
      assert payload["id"] == entry.id
      assert payload["accepted_at"] == DateTime.to_iso8601(entry.accepted_at)
      assert payload["public_key"]["key_id"] == entry.network_key_id

      # The digest the entry files the receipt under is the one the receipt
      # itself carries, so the row and the document cannot disagree about what
      # was signed.
      assert receipt["payload_digest"] == entry.receipt_digest

      assert entry.receipt_digest ==
               payload |> Techtree.Canonical.encode!() |> Techtree.Catalog.Digest.hash_bytes()
    end

    test "appends an acceptance event carrying the participant's own signature" do
      assert {:ok, entry, :recorded} = NetworkFixture.publish()

      assert [event] = Ingest.events(entry)

      assert event.kind == :accepted
      assert event.payload_digest == entry.bundle_digest
      assert event.participant_signature == NetworkFixture.manifest()["signature"]["signature"]
    end
  end

  describe "the checks" do
    setup :publish_the_catalog

    test "1. a body larger than a proof bundle can be is refused before it is read" do
      files = NetworkFixture.replace("receipts/baseline/0000.json", :binary.copy("0", 3_000_000))

      assert {:error, %{code: :submission_too_large, details: details}} =
               NetworkFixture.publish(NetworkFixture.submission(files))

      assert details["maximum_bytes"] == 2 * 1024 * 1024
    end

    test "2. a document with a fifth member, or a fourth missing, is not a submission" do
      smuggled =
        NetworkFixture.submission()
        |> Jason.decode!()
        |> Map.put("note", "arbitrary text nobody signed")
        |> Jason.encode!()

      assert {:error, %{code: :submission_malformed}} = NetworkFixture.publish(smuggled)

      for missing <- ["schema_version", "run_id", "bundle_digest", "files"] do
        body =
          NetworkFixture.submission() |> Jason.decode!() |> Map.delete(missing) |> Jason.encode!()

        assert {:error, %{code: :submission_malformed}} = NetworkFixture.publish(body)
      end

      assert Network.list_publication_entries!() == []
    end

    test "3. more files than a proof bundle can have is refused" do
      crowd =
        Map.new(1..300, fn number -> {"filler/#{number}.json", "{}"} end)

      files = Map.merge(NetworkFixture.files(), crowd)

      assert {:error, %{code: :submission_too_many_files, details: details}} =
               NetworkFixture.publish(NetworkFixture.submission(files))

      assert details["maximum_files"] == 256
      assert details["submitted_files"] == 384
    end

    test "4. a path a bundle cannot have is refused, and told which way it is wrong" do
      # The sentence is part of the refusal, not decoration: a participant
      # whose tooling wrote a Windows path and one whose tooling wrote an
      # absolute path have different things to fix.
      for {path, said} <- [
            {"/etc/passwd", "a path inside a bundle is relative"},
            {"../secrets.json", "a path names one file directly"},
            {"receipts\\baseline\\0000.json", "a path inside a bundle is written with /"},
            {"a//b.json", "a path names one file directly"},
            {"", "a path is not empty"}
          ] do
        files = Map.put(NetworkFixture.files(), path, "{}")

        assert {:error, %{code: :submission_path_invalid, details: details, message: message}} =
                 NetworkFixture.publish(NetworkFixture.submission(files)),
               "#{path} was not refused"

        assert details["path"] == path
        assert message =~ said
      end

      assert Network.list_publication_entries!() == []
    end

    test "4. the same path written twice is refused" do
      assert {:error, %{code: :submission_path_invalid, details: details}} =
               NetworkFixture.publish(
                 NetworkFixture.submission_with_repeated_path(@manifest_path)
               )

      assert details["repeated"] == [@manifest_path]
      assert Network.list_publication_entries!() == []
    end

    test "5. base64 written a second way is refused even though it decodes" do
      encoded =
        NetworkFixture.files()
        |> Map.new(fn {path, bytes} -> {path, Base.encode64(bytes)} end)
        # "e31=" decodes to the same two bytes "e30=" does, and is not how they
        # are spelled.
        |> Map.put("filler.json", "e31=")

      assert {:error, %{code: :submission_file_not_canonical_base64, details: details}} =
               NetworkFixture.publish(NetworkFixture.encoded_submission(encoded))

      assert details["path"] == "filler.json"
    end

    test "5. a file with no bytes in it is refused" do
      files = NetworkFixture.replace(@policy_path, "")

      assert {:error, %{code: :submission_file_empty, details: details}} =
               NetworkFixture.publish(NetworkFixture.submission(files))

      assert details["path"] == @policy_path
    end

    test "5. a file that is not base64 at all is refused" do
      assert {:error, %{code: :submission_malformed}} =
               NetworkFixture.publish(
                 NetworkFixture.encoded_submission(%{"bundle.json" => "not base64 !!"})
               )
    end

    test "6. a bundle with no manifest at its root is refused" do
      files = Map.delete(NetworkFixture.files(), @manifest_path)

      assert {:error, %{code: :submission_manifest_missing, details: details}} =
               NetworkFixture.publish(NetworkFixture.submission(files))

      assert details["path"] == @manifest_path
    end

    test "7. a file that does not hash to what the bundle claims is refused" do
      files = NetworkFixture.replace(@policy_path, ~s({"tampered":true}))

      assert {:error, %{code: :submission_artifact_digest_mismatch, details: details}} =
               NetworkFixture.publish(NetworkFixture.submission(files))

      assert details["path"] == @policy_path
    end

    test "7. a bundle that does not carry a file it lists is refused" do
      files = Map.delete(NetworkFixture.files(), "receipts/candidate/0007.json")

      assert {:error, %{code: :submission_artifact_missing, details: details}} =
               NetworkFixture.publish(NetworkFixture.submission(files))

      assert details["paths"] == ["receipts/candidate/0007.json"]
    end

    test "7. a bundle carrying a file it does not list is refused" do
      files = NetworkFixture.replace("receipts/candidate/9999.json", "{}")

      assert {:error, %{code: :submission_artifact_unlisted, details: details}} =
               NetworkFixture.publish(NetworkFixture.submission(files))

      assert details["paths"] == ["receipts/candidate/9999.json"]
    end

    test "8. a signed document that does not hash to the digest it carries is refused" do
      # The manifest is the one file no artifact list covers, so editing it
      # reaches the digest check rather than stopping at the check before.
      files =
        NetworkFixture.rewrite_payload(
          @manifest_path,
          &Map.put(&1, "run_id", "run_somebody_else")
        )

      assert {:error, %{code: :submission_payload_digest_mismatch, details: details}} =
               NetworkFixture.publish(NetworkFixture.submission(files))

      assert details["path"] == @manifest_path
    end

    test "9. a signature that does not verify under the bundle's own key is refused" do
      assert {:error, %{code: :submission_signature_invalid, details: details}} =
               NetworkFixture.publish(NetworkFixture.submission(unsigned_manifest()))

      assert details["path"] == @manifest_path
    end

    test "10. a key whose fingerprint is not that key's hash is refused" do
      # Signed properly throughout, under a key that calls itself something
      # else. Every signature verifies; the identifier is the lie.
      wrong = "sha256:" <> String.duplicate("b", 64)
      files = NetworkFixture.resign(NetworkFixture.files(), key_id: wrong)

      assert {:error, %{code: :submission_key_id_mismatch, details: details}} =
               NetworkFixture.publish(NetworkFixture.submission(files))

      assert details["claimed_key_id"] == wrong
    end

    test "11. a bundle committing to a result summary it does not carry is refused" do
      absent = "sha256:" <> String.duplicate("f", 64)
      files = NetworkFixture.resign(NetworkFixture.files(), root_report_digest: absent)

      assert {:error, %{code: :submission_report_missing, details: details}} =
               NetworkFixture.publish(NetworkFixture.submission(files))

      assert details["root_report_digest"] == absent
    end

    test "12. a campaign this site does not publish is refused" do
      files =
        NetworkFixture.files()
        |> Map.update!(@manifest_path, fn bytes ->
          bytes
          |> Jason.decode!()
          |> put_in(["payload", "campaign_spec_digest"], "sha256:" <> String.duplicate("c", 64))
          |> Jason.encode!()
        end)
        |> NetworkFixture.resign()

      assert {:error, %{code: :submission_campaign_unpublished, details: details}} =
               NetworkFixture.publish(NetworkFixture.submission(files))

      assert details["campaign_spec_digest"] == "sha256:" <> String.duplicate("c", 64)
    end

    test "13. a result whose counts do not recompute from its own tasks is refused" do
      files =
        rewritten_report(&update_in(&1, ["primary_result", "wins"], fn wins -> wins + 1 end))

      assert {:error, %{code: :submission_counts_inconsistent}} =
               NetworkFixture.publish(NetworkFixture.submission(files))
    end

    test "14. a result scoring tasks the campaign did not commit to is refused" do
      for damage <- [&Enum.reverse/1, &Enum.drop(&1, 1), &(&1 ++ &1)] do
        files = rewritten_report(&update_in(&1, ["task_deltas"], damage))

        assert {:error, %{code: code}} =
                 NetworkFixture.publish(NetworkFixture.submission(files))

        assert code in [:submission_task_membership_mismatch, :submission_counts_inconsistent]
      end
    end

    test "14. one task hash swapped for another is refused even with the counts intact" do
      files =
        rewritten_report(fn report ->
          update_in(report, ["task_deltas"], fn [first | rest] ->
            [Map.put(first, "task_hash", "sha256:" <> String.duplicate("d", 64)) | rest]
          end)
        end)

      assert {:error, %{code: :submission_task_membership_mismatch}} =
               NetworkFixture.publish(NetworkFixture.submission(files))
    end

    test "15. terms that do not make the result public refuse the publication" do
      for member <- ["uplift_report", "aggregate_scores"] do
        files =
          NetworkFixture.files()
          |> Map.update!(@policy_path, fn bytes ->
            bytes
            |> Jason.decode!()
            |> put_in(["derived_artifacts", member], "prohibited")
            |> Techtree.Canonical.encode!()
          end)
          |> NetworkFixture.resign()

        assert {:error, %{code: :submission_data_policy_forbids_publication, details: details}} =
                 NetworkFixture.publish(NetworkFixture.submission(files)),
               "#{member} being prohibited did not refuse the publication"

        assert details[member] == "prohibited"
      end

      assert Network.list_publication_entries!() == []
    end

    test "15. a bundle that does not carry the terms it names is refused" do
      absent = "sha256:" <> String.duplicate("9", 64)
      files = NetworkFixture.resign(NetworkFixture.files(), data_policy_digest: absent)

      assert {:error, %{code: :submission_data_policy_forbids_publication, details: details}} =
               NetworkFixture.publish(NetworkFixture.submission(files))

      assert details["data_policy_digest"] == absent
    end

    test "16. a document carrying a transcript is not a proof bundle" do
      for member <- ["transcript", "messages", "prompt", "stdout", "episodes"] do
        files =
          NetworkFixture.files()
          |> Map.update!("receipts/baseline/0000.json", fn bytes ->
            bytes
            |> Jason.decode!()
            |> update_in(["payload"], &Map.put(&1, member, "whatever was said"))
            |> Jason.encode!()
          end)
          |> NetworkFixture.resign()

        assert {:error, %{code: :submission_private_content, details: details}} =
                 NetworkFixture.publish(NetworkFixture.submission(files)),
               "a #{member} was not refused"

        assert details["member"] == member
        assert details["path"] == "receipts/baseline/0000.json"
      end

      assert Network.list_publication_entries!() == []
    end

    test "16. a document naming a location on the machine that made it is refused" do
      for location <- [
            "/Users/somebody/techtree/runs/run_x",
            "/home/somebody/.techtree",
            "C:\\Users\\somebody\\techtree",
            "~/techtree/runs"
          ] do
        files = rewritten_report(&Map.put(&1, "program_ref", location))

        assert {:error, %{code: :submission_private_content, details: details}} =
                 NetworkFixture.publish(NetworkFixture.submission(files)),
               "#{location} was not refused"

        assert details["path"] == @report_path
      end

      assert Network.list_publication_entries!() == []
    end

    test "17. a declared digest that is not the bundle's own is refused" do
      wrong = "sha256:" <> String.duplicate("e", 64)

      assert {:error, %{code: :submission_bundle_digest_mismatch, details: details}} =
               NetworkFixture.publish(
                 NetworkFixture.submission(NetworkFixture.files(), bundle_digest: wrong)
               )

      assert details["declared_bundle_digest"] == wrong
      assert details["bundle_digest"] == NetworkFixture.bundle_digest()
      assert Network.list_publication_entries!() == []
    end

    test "17. a declared run the signed report does not name is refused" do
      assert {:error, %{code: :submission_run_id_mismatch, details: details}} =
               NetworkFixture.publish(
                 NetworkFixture.submission(NetworkFixture.files(), run_id: "run_somebody_else")
               )

      assert details["declared_run_id"] == "run_somebody_else"
      assert details["run_id"] == NetworkFixture.report()["payload"]["run_id"]
      assert Network.list_publication_entries!() == []
    end

    test "17. is checked after the bundle itself, not instead of it" do
      # A bundle with a broken signature and a wrong declaration is refused for
      # the signature. What the submitter claims about a bundle means nothing
      # until the bundle has been shown to hold together.
      assert {:error, %{code: :submission_signature_invalid}} =
               NetworkFixture.publish(
                 NetworkFixture.submission(unsigned_manifest(), run_id: "run_somebody_else")
               )
    end

    test "the receipt names every check that ran, and there are as many as this site runs" do
      assert {:ok, entry, :recorded} = NetworkFixture.publish()

      checks = Jason.decode!(entry.receipt_bytes)["payload"]["checks"]

      assert length(checks) == Bundle.check_count()
      assert Enum.all?(checks, & &1["passed"])

      assert Enum.map(checks, & &1["id"]) ==
               Enum.map(Bundle.checks(), fn {id, _detail} -> to_string(id) end)
    end
  end

  describe "a refused submission" do
    setup :publish_the_catalog

    test "leaves nothing behind" do
      files = NetworkFixture.replace(@policy_path, ~s({"tampered":true}))

      assert {:error, _error} = NetworkFixture.publish(NetworkFixture.submission(files))
      assert Network.list_publication_entries!() == []
      assert Network.list_publication_events!() == []
    end

    test "is refused for the same reason however it is wrapped" do
      for body <- ["", "{}", "not json at all", ~s({"schema_version":"other","files":{}})] do
        assert {:error, %{code: :submission_malformed}} = NetworkFixture.publish(body)
      end
    end

    test "under the name the protocol used before this document had one is refused" do
      # The protocol names every document `techtree.<object>.v1alpha1`, and this
      # one is `techtree.publication-submission.v1alpha1`. A body under the old
      # spelling is not a submission, and there is no second name for it.
      renamed =
        NetworkFixture.submission()
        |> Jason.decode!()
        |> Map.put("schema_version", "techtree.submission.v1alpha1")
        |> Jason.encode!()

      assert {:error, %{code: :submission_malformed}} = NetworkFixture.publish(renamed)
      assert Network.list_publication_entries!() == []
    end
  end

  describe "idempotence by bundle digest" do
    setup :publish_the_catalog

    test "the first publication is recorded" do
      assert {:ok, entry, :recorded} = NetworkFixture.publish()
      assert length(Network.list_publication_entries!()) == 1
      assert entry.log_sequence >= 1
    end

    test "the same document again is the original entry and the original receipt" do
      assert {:ok, first, :recorded} = NetworkFixture.publish()
      assert {:ok, second, :existing} = NetworkFixture.publish()

      assert first.id == second.id
      assert first.log_sequence == second.log_sequence
      assert first.accepted_at == second.accepted_at
      assert first.receipt_bytes == second.receipt_bytes
      assert length(Network.list_publication_entries!()) == 1
      assert length(Network.list_publication_events!()) == 1
    end

    test "the same document wrapped differently for transport is still the same entry" do
      assert {:ok, first, :recorded} = NetworkFixture.publish()

      # The same document, written out with whitespace in it. A different
      # string of bytes carrying the same document, which is the same entry.
      rewrapped = NetworkFixture.submission() |> Jason.decode!() |> Jason.encode!(pretty: true)

      refute rewrapped == NetworkFixture.submission()
      assert {:ok, second, :existing} = NetworkFixture.publish(rewrapped)
      assert first.id == second.id
      assert first.receipt_bytes == second.receipt_bytes
    end

    test "the same digest carrying a different document is a conflict" do
      # Every honest submission carrying this bundle is the same four members
      # over the same files, so the only way this log holds one set of bytes
      # under a digest and is handed another is if something upstream of the
      # digest ever stopped being true. That is exactly what this branch is
      # for, so the row is seeded through the one door that writes rows, with
      # a digest of bytes nobody sent.
      held = NetworkFixture.seed_entry(submission_digest: "sha256:" <> String.duplicate("0", 64))

      assert {:error, %{code: :publication_bytes_conflict, details: details}} =
               NetworkFixture.publish()

      assert details["bundle_digest"] == held.bundle_digest
      assert details["log_sequence"] == held.log_sequence
      assert length(Network.list_publication_entries!()) == 1
    end

    test "the same participant and run under a different bundle is a conflict" do
      keys = NetworkFixture.key_pair()

      first = NetworkFixture.resign(NetworkFixture.files(), keys: keys)
      assert {:ok, _entry, :recorded} = NetworkFixture.publish(NetworkFixture.submission(first))

      # The same run, signed by the same key, in a bundle whose bytes differ:
      # one episode receipt is re-sealed, so every digest downstream of it
      # changes and the bundle addresses differently.
      second =
        first
        |> Map.update!("receipts/baseline/0000.json", fn bytes ->
          bytes
          |> Jason.decode!()
          |> update_in(["payload"], &Map.put(&1, "score_status", "valid "))
          |> Jason.encode!()
        end)
        |> NetworkFixture.resign(keys: keys)

      assert {:error, %{code: :publication_run_conflict, details: details}} =
               NetworkFixture.publish(NetworkFixture.submission(second))

      assert details["run_id"] == NetworkFixture.report()["payload"]["run_id"]
      assert length(Network.list_publication_entries!()) == 1
    end

    test "two identical publications racing leave one row and two identical receipts" do
      # The sandbox gives every process the same connection, so these do not
      # overlap inside Postgres. What they do prove is that the path both of
      # them take is the same one — there is no "does it exist yet" query in
      # front of the insert, so the second is refused by the unique index and
      # recovers the first one's row, which is exactly what the loser of a real
      # race does.
      Ecto.Adapters.SQL.Sandbox.mode(Techtree.Repo, {:shared, self()})

      [first, second] =
        [1, 2]
        |> Enum.map(fn _attempt -> Task.async(fn -> NetworkFixture.publish() end) end)
        |> Task.await_many(30_000)

      assert {:ok, one, _} = first
      assert {:ok, two, _} = second

      assert one.id == two.id
      assert one.receipt_bytes == two.receipt_bytes
      assert length(Network.list_publication_entries!()) == 1

      outcomes = [elem(first, 2), elem(second, 2)]
      assert Enum.sort(outcomes) == [:existing, :recorded]
    end
  end

  describe "withdrawal" do
    setup :publish_the_catalog

    setup do
      keys = NetworkFixture.key_pair()
      files = NetworkFixture.resign(NetworkFixture.files(), keys: keys)

      {:ok, entry, :recorded} = NetworkFixture.publish(NetworkFixture.submission(files))

      {:ok, keys: keys, entry: entry}
    end

    test "is an appended event, and the entry keeps everything it had", context do
      %{keys: keys, entry: entry} = context

      assert {:ok, withdrawn, :recorded} =
               Ingest.withdraw(NetworkFixture.withdrawal(entry.bundle_digest, keys))

      assert withdrawn.id == entry.id
      assert withdrawn.log_sequence == entry.log_sequence
      assert withdrawn.submission_bytes == entry.submission_bytes
      assert withdrawn.receipt_bytes == entry.receipt_bytes
      assert withdrawn.wins == entry.wins
      refute is_nil(withdrawn.withdrawn_at)

      assert [%{kind: :accepted}, %{kind: :withdrawn} = event] = Ingest.events(entry)
      assert event.payload_digest != entry.bundle_digest
      assert is_binary(event.participant_signature)
    end

    test "leaves the entry on the log, at its own address", context do
      %{keys: keys, entry: entry} = context

      Ingest.withdraw(NetworkFixture.withdrawal(entry.bundle_digest, keys))

      assert %{entries: [listed]} = Techtree.Network.Query.page()
      assert listed.bundle_digest == entry.bundle_digest
      refute is_nil(listed.withdrawn_at)

      assert {:ok, _found} = Techtree.Network.Query.get_entry(entry.bundle_digest)
    end

    test "signed by anybody else is refused", context do
      %{entry: entry} = context

      assert {:error, %{code: :withdrawal_signature_invalid}} =
               Ingest.withdraw(
                 NetworkFixture.withdrawal(entry.bundle_digest, NetworkFixture.key_pair())
               )

      assert {:ok, held} = Techtree.Network.Query.get_entry(entry.bundle_digest)
      assert is_nil(held.withdrawn_at)
    end

    test "claiming somebody else's key id is refused", context do
      %{entry: entry} = context

      other = NetworkFixture.key_pair()

      assert {:error, %{code: :withdrawal_signature_invalid}} =
               Ingest.withdraw(
                 NetworkFixture.withdrawal(entry.bundle_digest, other,
                   key_id: entry.participant_key_id
                 )
               )
    end

    test "whose digest is not the digest of what it carries is refused", context do
      %{keys: keys, entry: entry} = context

      assert {:error, %{code: :withdrawal_malformed}} =
               Ingest.withdraw(
                 NetworkFixture.withdrawal(entry.bundle_digest, keys,
                   payload_digest: "sha256:" <> String.duplicate("a", 64)
                 )
               )
    end

    test "carrying anything beside its three members is refused", context do
      %{keys: keys, entry: entry} = context

      settled = %{
        "schema_version" => "techtree.publication-withdrawal.v1alpha1",
        "bundle_digest" => entry.bundle_digest,
        "requested_at" => DateTime.to_iso8601(DateTime.utc_now())
      }

      # The settled shape goes through, so the refusals below are about the
      # fourth member and the missing one rather than about the shape being
      # wrong in some other way this test cannot see.
      assert {:ok, _entry, :recorded} =
               Ingest.withdraw(
                 NetworkFixture.withdrawal(entry.bundle_digest, keys, payload: settled)
               )

      for payload <- [
            Map.put(settled, "reason", "changed my mind"),
            Map.delete(settled, "requested_at"),
            Map.delete(settled, "bundle_digest") |> Map.put("bundle", entry.bundle_digest)
          ] do
        assert {:error, %{code: :withdrawal_malformed}} =
                 Ingest.withdraw(
                   NetworkFixture.withdrawal(entry.bundle_digest, keys, payload: payload)
                 )
      end
    end

    test "naming a run this log does not hold is refused", context do
      %{keys: keys} = context

      absent = "sha256:" <> String.duplicate("7", 64)

      assert {:error, %{code: :withdrawal_entry_missing}} =
               Ingest.withdraw(NetworkFixture.withdrawal(absent, keys))
    end

    test "twice appends one event", context do
      %{keys: keys, entry: entry} = context

      assert {:ok, _first, :recorded} =
               Ingest.withdraw(NetworkFixture.withdrawal(entry.bundle_digest, keys))

      assert {:ok, _second, :existing} =
               Ingest.withdraw(NetworkFixture.withdrawal(entry.bundle_digest, keys))

      assert Enum.count(Ingest.events(entry), &(&1.kind == :withdrawn)) == 1
    end
  end

  describe "an address somebody volunteered" do
    setup :publish_the_catalog

    @address "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"
    @second_address "0xde709f2102306220921060314715629080e2fb77"

    test "is stored apart from the log, keyed by the address itself, never on the entry" do
      {:ok, entry, :recorded} =
        NetworkFixture.publish(NetworkFixture.submission(), contributor_address: @address)

      record = Ingest.contributor_address(@address)

      assert record.address == String.downcase(@address)
      assert record.submission_count == 1
      assert record.publication_id == entry.id
      assert record.first_seen_at == record.last_seen_at

      refute entry |> Map.from_struct() |> Map.values() |> Enum.any?(&(&1 == @address))
      refute entry.receipt_bytes =~ @address
      refute entry.receipt_bytes =~ String.downcase(@address)
      refute entry.submission_bytes =~ String.downcase(@address)
    end

    test "left again with a second run is one row counting two, pointing at the newer run" do
      {:ok, first, :recorded} =
        NetworkFixture.publish(NetworkFixture.submission(), contributor_address: @address)

      before = Ingest.contributor_address(@address)

      {:ok, second, :recorded} =
        NetworkFixture.publish(another_run(), contributor_address: @address)

      record = Ingest.contributor_address(@address)

      assert record.submission_count == 2
      assert record.publication_id == second.id
      refute record.publication_id == first.id
      assert record.first_seen_at == before.first_seen_at
      assert DateTime.compare(record.last_seen_at, before.last_seen_at) in [:gt, :eq]

      assert length(Network.list_publication_entries!()) == 2
    end

    test "spelled the other way is the same row, because case is not identity" do
      NetworkFixture.publish(NetworkFixture.submission(), contributor_address: @address)

      NetworkFixture.publish(another_run(),
        contributor_address: String.downcase(@address)
      )

      assert Ingest.contributor_address(@address).submission_count == 2
    end

    test "is one row per address and not one per publisher" do
      NetworkFixture.publish(NetworkFixture.submission(), contributor_address: @address)
      NetworkFixture.publish(another_run(), contributor_address: @second_address)

      assert Ingest.contributor_address(@address).submission_count == 1
      assert Ingest.contributor_address(@second_address).submission_count == 1
    end

    test "is refused, with the submission, when a character of it is wrong" do
      damaged = "0x5aAeb6053f3E94C9b9A09f33669435E7Ef1BeAed"

      assert {:error, %{code: :contributor_address_invalid}} =
               NetworkFixture.publish(NetworkFixture.submission(),
                 contributor_address: damaged
               )

      assert Network.list_publication_entries!() == []
    end

    test "is never named in the refusal that turned it down" do
      damaged = "0x5aAeb6053f3E94C9b9A09f33669435E7Ef1BeAed"

      {:error, error} =
        NetworkFixture.publish(NetworkFixture.submission(), contributor_address: damaged)

      said = Jason.encode!(%{message: error.message, details: error.details})

      refute said =~ damaged
      refute said =~ String.downcase(damaged)
    end

    test "removal means removal from the active system, however many runs supplied it" do
      NetworkFixture.publish(NetworkFixture.submission(), contributor_address: @address)
      NetworkFixture.publish(another_run(), contributor_address: @address)

      assert Ingest.contributor_address(@address).submission_count == 2

      assert :ok = Ingest.forget_contributor_address(String.downcase(@address))
      assert Ingest.contributor_address(@address) == nil
      assert length(Network.list_publication_entries!()) == 2
    end

    test "cannot be reached through the domain by anything but the ingest" do
      NetworkFixture.publish(NetworkFixture.submission(), contributor_address: @address)

      assert {:error, _forbidden} = Network.list_contributor_addresses()
      assert {:error, _forbidden} = Network.get_contributor_address(String.downcase(@address))
    end
  end

  # A second real publication by a second participant: the same proof, signed
  # again under a key made here, which is a different bundle and therefore a
  # different entry. It is what a second person leaving the same address looks
  # like, and what this table is unable to tell apart from one person doing it
  # twice — correctly, because nobody proved control of the address either way.
  defp another_run do
    NetworkFixture.files()
    |> NetworkFixture.resign()
    |> NetworkFixture.submission()
  end

  defp publish_the_catalog(_context) do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())
    :ok
  end

  defp unsigned_manifest do
    NetworkFixture.replace(
      @manifest_path,
      NetworkFixture.files()
      |> Map.fetch!(@manifest_path)
      |> Jason.decode!()
      |> put_in(["signature", "signature"], Base.encode64(:binary.copy(<<0>>, 64)))
      |> Jason.encode!()
    )
  end

  defp rewritten_report(transform) do
    NetworkFixture.files()
    |> Map.update!(@report_path, fn bytes ->
      bytes |> Jason.decode!() |> update_in(["payload"], transform) |> Jason.encode!()
    end)
    |> NetworkFixture.resign()
  end
end
