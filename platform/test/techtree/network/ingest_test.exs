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
  so the tests for the last three checks hand over a bundle that is perfectly
  signed under a key made for the occasion and simply wrong about what it
  claims. That is the case worth refusing: not a bundle somebody broke, but one
  somebody built.
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

  describe "with nothing published to anchor a run to" do
    test "an honest bundle is refused, because the campaign it names is not ours" do
      assert {:error, %{code: :submission_campaign_unpublished}} =
               Ingest.accept(NetworkFixture.submission())

      assert Network.list_submissions!() == []
    end
  end

  describe "a real proof bundle" do
    setup :publish_the_catalog

    test "is accepted, and every published field is recomputed rather than copied" do
      assert {:ok, entry, :recorded} = Ingest.accept(NetworkFixture.submission())

      report = NetworkFixture.report()["payload"]
      manifest = NetworkFixture.manifest()["payload"]

      assert entry.sequence >= 1
      assert entry.bundle_digest == NetworkFixture.bundle_digest()
      assert entry.run_id == manifest["run_id"]
      assert entry.campaign_spec_digest == manifest["campaign_spec_digest"]
      assert entry.data_policy_digest == manifest["data_policy_digest"]
      assert entry.climb_reference == CatalogFixture.climb_reference()
      assert entry.executor_kind == :local_ed25519
      assert entry.executor_key_id == manifest["executor_identity"]["key_id"]
      assert entry.subject_harness == "hermes-agent"
      assert entry.subject_harness_version == "0.19.0"
      assert entry.subject_model == "qwen/qwen3.7-flash"
      assert entry.wins == report["primary_result"]["wins"]
      assert entry.losses == report["primary_result"]["losses"]
      assert entry.ties == report["primary_result"]["ties"]
      assert entry.task_count == 36
      assert length(entry.task_deltas) == 36
      assert entry.decision == "accepted"
      assert entry.proof_grade == "P1"
      assert entry.verification_checks_run == Bundle.check_count()
      assert entry.verification_checks_passed == Bundle.check_count()
      assert entry.raw_payload == NetworkFixture.submission()
      assert is_nil(entry.withdrawn_at)
    end

    test "sent twice is one entry, at the position it already had" do
      assert {:ok, first, :recorded} = Ingest.accept(NetworkFixture.submission())
      assert {:ok, second, :existing} = Ingest.accept(NetworkFixture.submission())

      assert first.id == second.id
      assert first.sequence == second.sequence
      assert length(Network.list_submissions!()) == 1
    end

    test "wrapped differently for transport is still the same entry" do
      assert {:ok, first, :recorded} = Ingest.accept(NetworkFixture.submission())

      # The same document, written out with whitespace in it. A different
      # string of bytes carrying the same proof, which is the same entry.
      rewrapped =
        NetworkFixture.submission() |> Jason.decode!() |> Jason.encode!(pretty: true)

      refute rewrapped == NetworkFixture.submission()
      assert {:ok, second, :existing} = Ingest.accept(rewrapped)
      assert first.id == second.id
    end
  end

  describe "the eight checks" do
    setup :publish_the_catalog

    test "1. a body larger than a proof bundle can be is refused before it is read" do
      files = NetworkFixture.replace("receipts/baseline/0000.json", :binary.copy("0", 4_000_000))

      assert {:error, %{code: :submission_too_large}} =
               Ingest.accept(NetworkFixture.submission(files))
    end

    test "2. a file that does not hash to what the bundle claims is refused" do
      files = NetworkFixture.replace("data-policy.json", ~s({"tampered":true}))

      assert {:error, %{code: :submission_artifact_digest_mismatch, details: details}} =
               Ingest.accept(NetworkFixture.submission(files))

      assert details["path"] == "data-policy.json"
    end

    test "2. a bundle that does not carry a file it lists is refused" do
      files = Map.delete(NetworkFixture.files(), "receipts/candidate/0007.json")

      assert {:error, %{code: :submission_artifact_missing, details: details}} =
               Ingest.accept(NetworkFixture.submission(files))

      assert details["paths"] == ["receipts/candidate/0007.json"]
    end

    test "2. a bundle carrying a file it does not list is refused" do
      files = NetworkFixture.replace("receipts/candidate/9999.json", "{}")

      assert {:error, %{code: :submission_artifact_unlisted, details: details}} =
               Ingest.accept(NetworkFixture.submission(files))

      assert details["paths"] == ["receipts/candidate/9999.json"]
    end

    test "3. a signed document that does not hash to the digest it carries is refused" do
      # The manifest is the one file no artifact list covers, so editing it
      # reaches the digest check rather than stopping at the check before.
      files =
        NetworkFixture.rewrite_payload(
          @manifest_path,
          &Map.put(&1, "run_id", "run_somebody_else")
        )

      assert {:error, %{code: :submission_payload_digest_mismatch, details: details}} =
               Ingest.accept(NetworkFixture.submission(files))

      assert details["path"] == @manifest_path
    end

    test "4. a signature that does not verify under the bundle's own key is refused" do
      files =
        NetworkFixture.replace(
          @manifest_path,
          NetworkFixture.files()
          |> Map.fetch!(@manifest_path)
          |> Jason.decode!()
          |> put_in(["signature", "signature"], Base.encode64(:binary.copy(<<0>>, 64)))
          |> Jason.encode!()
        )

      assert {:error, %{code: :submission_signature_invalid, details: details}} =
               Ingest.accept(NetworkFixture.submission(files))

      assert details["path"] == @manifest_path
    end

    test "5. a key whose fingerprint is not that key's hash is refused" do
      # Signed properly throughout, under a key that calls itself something
      # else. Every signature verifies; the identifier is the lie.
      wrong = "sha256:" <> String.duplicate("b", 64)
      files = NetworkFixture.resign(NetworkFixture.files(), key_id: wrong)

      assert {:error, %{code: :submission_key_id_mismatch, details: details}} =
               Ingest.accept(NetworkFixture.submission(files))

      assert details["claimed_key_id"] == wrong
    end

    test "6. a campaign this site does not publish is refused" do
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
               Ingest.accept(NetworkFixture.submission(files))

      assert details["campaign_spec_digest"] == "sha256:" <> String.duplicate("c", 64)
    end

    test "7. a result whose counts do not recompute from its own tasks is refused" do
      files =
        NetworkFixture.files()
        |> Map.update!(@report_path, fn bytes ->
          bytes
          |> Jason.decode!()
          |> update_in(["payload", "primary_result", "wins"], &(&1 + 1))
          |> Jason.encode!()
        end)
        |> NetworkFixture.resign()

      assert {:error, %{code: :submission_counts_inconsistent}} =
               Ingest.accept(NetworkFixture.submission(files))
    end

    test "8. a result scoring tasks the campaign did not commit to is refused" do
      for damage <- [&Enum.reverse/1, &Enum.drop(&1, 1), &(&1 ++ &1)] do
        files =
          NetworkFixture.files()
          |> Map.update!(@report_path, fn bytes ->
            bytes
            |> Jason.decode!()
            |> update_in(["payload", "task_deltas"], damage)
            |> Jason.encode!()
          end)
          |> NetworkFixture.resign()

        assert {:error, %{code: code}} = Ingest.accept(NetworkFixture.submission(files))

        assert code in [:submission_task_membership_mismatch, :submission_counts_inconsistent]
      end
    end

    test "8. one task hash swapped for another is refused even with the counts intact" do
      files =
        NetworkFixture.files()
        |> Map.update!(@report_path, fn bytes ->
          bytes
          |> Jason.decode!()
          |> update_in(["payload", "task_deltas"], fn [first | rest] ->
            [Map.put(first, "task_hash", "sha256:" <> String.duplicate("d", 64)) | rest]
          end)
          |> Jason.encode!()
        end)
        |> NetworkFixture.resign()

      assert {:error, %{code: :submission_task_membership_mismatch}} =
               Ingest.accept(NetworkFixture.submission(files))
    end
  end

  describe "a refused submission" do
    setup :publish_the_catalog

    test "leaves nothing behind" do
      files = NetworkFixture.replace("data-policy.json", ~s({"tampered":true}))

      assert {:error, _error} = Ingest.accept(NetworkFixture.submission(files))
      assert Network.list_submissions!() == []
    end

    test "is refused for the same reason however it is wrapped" do
      for body <- [
            "",
            "{}",
            "not json at all",
            ~s({"schema_version":"other","files":{}}),
            Jason.encode!(
              NetworkFixture.submission()
              |> Jason.decode!()
              |> Map.put("note", "read me")
            )
          ] do
        assert {:error, %{code: :submission_malformed}} = Ingest.accept(body)
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

      assert {:error, %{code: :submission_malformed}} = Ingest.accept(renamed)
      assert Network.list_submissions!() == []
    end

    test "carrying anything beside its four members is refused" do
      # A submission's bytes are stored and served back at a public address, so
      # a document that allowed a fifth member would be a way to have this site
      # host whatever somebody put in it.
      smuggled =
        NetworkFixture.submission()
        |> Jason.decode!()
        |> Map.put("note", "arbitrary text nobody signed")
        |> Jason.encode!()

      assert {:error, %{code: :submission_malformed}} = Ingest.accept(smuggled)
      assert Network.list_submissions!() == []
    end

    test "declaring less than the four members is refused" do
      for missing <- ["schema_version", "run_id", "bundle_digest", "files"] do
        body =
          NetworkFixture.submission()
          |> Jason.decode!()
          |> Map.delete(missing)
          |> Jason.encode!()

        assert {:error, %{code: :submission_malformed}} = Ingest.accept(body)
      end

      assert Network.list_submissions!() == []
    end

    test "carrying a file that is not base64 is refused" do
      body =
        Jason.encode!(%{
          "schema_version" => "techtree.publication-submission.v1alpha1",
          "run_id" => "run_c4758ddb5bba4023aa3530b47f4582e9",
          "bundle_digest" => NetworkFixture.bundle_digest(),
          "files" => %{"bundle.json" => "not base64 !!"}
        })

      assert {:error, %{code: :submission_malformed}} = Ingest.accept(body)
    end
  end

  describe "what a submission claims about the bundle it carries" do
    setup :publish_the_catalog

    test "a declared digest that is not the bundle's own is refused" do
      wrong = "sha256:" <> String.duplicate("e", 64)

      assert {:error, %{code: :submission_bundle_digest_mismatch, details: details}} =
               Ingest.accept(
                 NetworkFixture.submission(NetworkFixture.files(), bundle_digest: wrong)
               )

      assert details["declared_bundle_digest"] == wrong
      assert details["bundle_digest"] == NetworkFixture.bundle_digest()
      assert Network.list_submissions!() == []
    end

    test "a declared run the signed report does not name is refused" do
      assert {:error, %{code: :submission_run_id_mismatch, details: details}} =
               Ingest.accept(
                 NetworkFixture.submission(NetworkFixture.files(), run_id: "run_somebody_else")
               )

      assert details["declared_run_id"] == "run_somebody_else"
      assert details["run_id"] == NetworkFixture.report()["payload"]["run_id"]
      assert Network.list_submissions!() == []
    end

    test "is checked after the bundle itself, not instead of it" do
      # A bundle with a broken signature and a wrong declaration is refused for
      # the signature. What the submitter claims about a bundle means nothing
      # until the bundle has been shown to hold together.
      files =
        NetworkFixture.replace(
          @manifest_path,
          NetworkFixture.files()
          |> Map.fetch!(@manifest_path)
          |> Jason.decode!()
          |> put_in(["signature", "signature"], Base.encode64(:binary.copy(<<0>>, 64)))
          |> Jason.encode!()
        )

      assert {:error, %{code: :submission_signature_invalid}} =
               Ingest.accept(NetworkFixture.submission(files, run_id: "run_somebody_else"))
    end

    test "agreeing is what an honest submission does, and it is recorded from the bundle" do
      assert {:ok, entry, :recorded} = Ingest.accept(NetworkFixture.submission())

      assert entry.run_id == NetworkFixture.report()["payload"]["run_id"]
      assert entry.bundle_digest == NetworkFixture.bundle_digest()
    end
  end

  describe "withdrawal" do
    setup :publish_the_catalog

    test "is an appended event, and the entry keeps everything it had" do
      {:ok, entry, :recorded} = Ingest.accept(NetworkFixture.submission())

      withdrawn = Ingest.withdraw(entry, :requested_by_publisher)

      assert withdrawn.id == entry.id
      assert withdrawn.raw_payload == entry.raw_payload
      assert withdrawn.wins == entry.wins
      assert not is_nil(withdrawn.withdrawn_at)

      assert [%{reason: :requested_by_publisher, submission_id: id}] = Network.list_withdrawals!()
      assert id == entry.id

      assert Network.list_published_submissions!() == []
      assert {:ok, %{}} = Network.get_submission_by_digest(entry.bundle_digest)
    end
  end

  describe "an address somebody volunteered" do
    setup :publish_the_catalog

    @address "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"

    test "is stored apart from the log, keyed lowercase, and never on the entry" do
      {:ok, entry, :recorded} =
        Ingest.accept(NetworkFixture.submission(), contributor_address: @address)

      record = Ingest.contributor_address(String.downcase(@address))

      assert record.address == String.downcase(@address)
      assert record.submission_count == 1
      assert record.submission_id == entry.id

      refute entry |> Map.from_struct() |> Map.values() |> Enum.any?(&(&1 == @address))
    end

    test "counted again when a second entry supplies the same address in another spelling" do
      {:ok, _first, :recorded} =
        Ingest.accept(NetworkFixture.submission(), contributor_address: @address)

      {:ok, second, :recorded} =
        Ingest.accept(
          NetworkFixture.submission(NetworkFixture.resign(NetworkFixture.files())),
          contributor_address: "0x" <> String.upcase(String.slice(@address, 2..-1//1))
        )

      record = Ingest.contributor_address(String.downcase(@address))

      assert record.submission_count == 2
      assert record.submission_id == second.id
      assert length(Network.list_submissions!()) == 2
    end

    test "is refused, with the submission, when a character of it is wrong" do
      damaged = "0x5aAeb6053f3E94C9b9A09f33669435E7Ef1BeAed"

      assert {:error, %{code: :contributor_address_invalid}} =
               Ingest.accept(NetworkFixture.submission(), contributor_address: damaged)

      assert Network.list_submissions!() == []
    end

    test "removal means removal" do
      {:ok, _entry, :recorded} =
        Ingest.accept(NetworkFixture.submission(), contributor_address: @address)

      assert :ok = Ingest.forget_contributor_address(String.downcase(@address))
      assert is_nil(Ingest.contributor_address(String.downcase(@address)))
      assert length(Network.list_submissions!()) == 1
    end
  end

  defp publish_the_catalog(_context) do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())
    :ok
  end
end
