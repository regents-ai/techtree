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
  """

  use Techtree.DataCase, async: false

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture
  alias Techtree.Network.Bundle
  alias Techtree.Network.Ingest

  @conformance Path.expand(
                 "../../../../techtree-python/tests/fixtures/publication/conformance-submission.json",
                 __DIR__
               )

  setup do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())
    :ok
  end

  test "the submission techtree-python builds for a real run is accepted here unmodified" do
    submitted = File.read!(@conformance)

    assert {:ok, entry, :recorded} = Ingest.accept(submitted)

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
    assert entry.raw_payload == submitted
  end
end
