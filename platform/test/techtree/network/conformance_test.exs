defmodule Techtree.Network.ConformanceTest do
  @moduledoc """
  The bytes the other half of this feature actually sends.

  Everything else in this suite builds a submission out of a real proof bundle
  using this repository's own fixture helper, which proves that the ingest
  agrees with this repository's reading of the wire contract. That is the one
  thing it was never in doubt about. The two halves of publishing were built at
  once from opposite ends and disagreed on four things, so the claim worth
  testing is a different one: that the document `techtree-python`'s real
  publishing path produces for a real 36-task run is accepted here, unmodified,
  byte for byte.

  `techtree-python` writes that document to
  `tests/fixtures/publication/conformance-submission.json` and this test reads
  it from there rather than from a copy kept here. A copy would agree with
  whatever it was copied from on the day it was copied, which is exactly the
  drift the wire contract in decision 0038 was written down to stop. If that
  file is not where it should be, this test fails, because a conformance claim
  nobody can check is not a conformance claim.

  The same is done in the other direction for what this site sends back. The
  two receipts and the withdrawal request are exported as JSON Schemas in
  `techtree-python/schemas/v1alpha1`, with `additionalProperties: false` and an
  explicit `required` list, so the member set of each document is fixed there
  rather than described here. These tests read those files and check the
  documents this site actually produces against them, member for member. That
  is what caught the last disagreement: the receipt was a flat document on one
  side and a signed envelope on the other, and either would have passed a test
  written against its own author's reading.

  The same fixture is read a third time, backwards. This site builds
  submissions of its own when it seeds the log with the certification runs, and
  a submission built here that merely resembled the CLI's would be the wire
  contract drifting from the inside. So the fixture is decoded back into a
  proof directory, a submission is built from that directory by the code the
  seeding uses, and the two are compared byte for byte.
  """

  use Techtree.DataCase, async: false

  alias Techtree.Canonical
  alias Techtree.Catalog.Digest
  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture
  alias Techtree.Network.Bundle
  alias Techtree.Network.Key
  alias Techtree.Network.Receipt
  alias Techtree.Network.Seed
  alias Techtree.NetworkFixture

  @conformance Path.expand(
                 "../../../../techtree-python/tests/fixtures/publication/conformance-submission.json",
                 __DIR__
               )

  @schemas Path.expand("../../../../techtree-python/schemas/v1alpha1", __DIR__)

  setup do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())
    :ok
  end

  test "the submission techtree-python builds for a real run is accepted here unmodified" do
    submitted = File.read!(@conformance)

    assert {:ok, entry, :recorded} = NetworkFixture.publish(submitted)

    declared = Jason.decode!(submitted)

    assert declared["schema_version"] == "techtree.publication-submission.v1alpha1"
    assert Enum.sort(Map.keys(declared)) == ~w(bundle_digest files run_id schema_version)
    assert is_map(declared["files"])

    # What the sender declared and what the site recorded are the same facts,
    # arrived at from opposite directions: the sender read them off its own
    # bundle, and the site recomputed them from the signed bytes.
    assert entry.bundle_digest == declared["bundle_digest"]
    assert entry.run_id == declared["run_id"]
    assert entry.task_count == 36
    assert entry.verification_checks_passed == Bundle.check_count()
    assert entry.submission_bytes == submitted
  end

  test "the submission this site builds for a proof directory is the one techtree-python sends" do
    submitted = File.read!(@conformance)

    # The fixture carries every byte of the proof it was built from, so the
    # directory can be rebuilt from it and the submission rebuilt from the
    # directory, with nothing needed that is not committed. That is what makes
    # this a conformance check rather than a comparison of two copies of the
    # same string: the bytes go back through the shape and come out again.
    directory = Path.join(tmp_dir(), "proof")

    for {path, encoded} <- Jason.decode!(submitted)["files"] do
      written = Path.join(directory, path)
      File.mkdir_p!(Path.dirname(written))
      File.write!(written, Base.decode64!(encoded))
    end

    assert Seed.submission(directory) == submitted
  end

  describe "against the schemas techtree-python exports" do
    test "a publication receipt is the envelope its schema fixes" do
      {:ok, entry, :recorded} = NetworkFixture.publish()
      {:ok, key} = Key.load()

      receipt = Receipt.issue(entry, TechtreeWeb.Endpoint.url(), key)

      conforms(receipt, "publication-receipt.schema.json", "PublicationReceiptPayload")

      assert receipt["payload"]["schema_version"] == "techtree.publication-receipt.v1alpha1"

      # And the bytes actually stored on the entry are that same document.
      assert Jason.decode!(entry.receipt_bytes) == receipt
    end

    test "a withdrawal receipt is the envelope its schema fixes" do
      keys = NetworkFixture.key_pair()
      files = NetworkFixture.resign(NetworkFixture.files(), keys: keys)

      {:ok, entry, :recorded} = NetworkFixture.publish(NetworkFixture.submission(files))

      {:ok, withdrawn, :recorded} =
        Techtree.Network.Ingest.withdraw(NetworkFixture.withdrawal(entry.bundle_digest, keys))

      {:ok, key} = Key.load()

      receipt = Receipt.issue_withdrawal(withdrawn, TechtreeWeb.Endpoint.url(), key)

      conforms(
        receipt,
        "publication-withdrawal-receipt.schema.json",
        "WithdrawalReceiptPayload"
      )

      assert receipt["payload"]["schema_version"] ==
               "techtree.publication-withdrawal-receipt.v1alpha1"
    end

    test "the withdrawal request this site accepts is the one its schema fixes" do
      keys = NetworkFixture.key_pair()
      files = NetworkFixture.resign(NetworkFixture.files(), keys: keys)

      {:ok, entry, :recorded} = NetworkFixture.publish(NetworkFixture.submission(files))

      request = Jason.decode!(NetworkFixture.withdrawal(entry.bundle_digest, keys))

      conforms(request, "publication-withdrawal.schema.json", "WithdrawalRequest")

      assert {:ok, _checked} =
               Techtree.Network.WithdrawalRequest.verify(
                 NetworkFixture.withdrawal(entry.bundle_digest, keys),
                 entry
               )
    end
  end

  defp tmp_dir do
    directory =
      Path.join(System.tmp_dir!(), "techtree-conformance-#{System.unique_integer([:positive])}")

    File.mkdir_p!(directory)
    on_exit(fn -> File.rm_rf!(directory) end)

    directory
  end

  # An envelope, checked against the schema's own two member lists rather than
  # against a list written here: the three envelope members, and the payload
  # members the named definition requires. Both schemas say
  # `additionalProperties: false`, so "exactly these" is what conformance means.
  defp conforms(document, file, definition) do
    assert Enum.sort(Map.keys(document)) == ["payload", "payload_digest", "signature"]

    assert document["payload_digest"] ==
             document["payload"] |> Canonical.encode!() |> Digest.hash_bytes()

    assert Enum.sort(Map.keys(document["signature"])) == ~w(algorithm key_id signature)

    members(document["payload"], file, definition)
  end

  defp members(payload, file, definition) do
    schema = @schemas |> Path.join(file) |> File.read!() |> Jason.decode!()
    fixed = schema["$defs"][definition]

    assert Enum.sort(Map.keys(payload)) == Enum.sort(fixed["required"])
    assert Enum.sort(Map.keys(payload)) == Enum.sort(Map.keys(fixed["properties"]))
    assert fixed["additionalProperties"] == false
  end
end
