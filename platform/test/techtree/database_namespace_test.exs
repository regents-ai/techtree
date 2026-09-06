defmodule Techtree.DatabaseNamespaceTest do
  use ExUnit.Case, async: false

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture
  alias Techtree.Network
  alias Techtree.NetworkFixture
  alias Techtree.Repo

  setup do
    unless Repo.config()[:database] == "techtree_test" <> System.fetch_env!("MIX_TEST_PARTITION") do
      raise "Namespace tests require the prepared disposable database"
    end

    original = Application.fetch_env!(:techtree, Repo)
    on_exit(fn -> Application.put_env(:techtree, Repo, original) end)
    Application.put_env(:techtree, Repo, Keyword.put(original, :default_prefix, "techtree_app"))
    dynamic = start_supervised!({Repo, name: nil, pool_size: 2})
    Repo.put_dynamic_repo(dynamic)
    :ok = Ecto.Adapters.SQL.Sandbox.checkout(dynamic)

    Repo.query!("CREATE SCHEMA techtree_app")

    for table <-
          ~w(catalog_releases catalog_entries bootstrap_releases network_publication_entries network_publication_events network_contributor_addresses_by_participant schema_migrations) do
      Repo.query!("CREATE TABLE techtree_app.#{table} (LIKE public.#{table} INCLUDING ALL)")
    end

    Repo.query!(
      "INSERT INTO techtree_app.schema_migrations SELECT * FROM public.schema_migrations"
    )

    Repo.query!("CREATE SEQUENCE techtree_app.network_publication_sequence START 900001")
    :ok
  end

  test "publishing and retrying use the selected tables and sequence with exact receipt bytes" do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())

    public_sequence =
      Repo.query!("SELECT last_value, is_called FROM public.network_publication_sequence").rows

    public_rows = Repo.query!("SELECT count(*) FROM public.network_publication_entries").rows
    submission = NetworkFixture.submission()

    assert {:ok, entry, :recorded} = NetworkFixture.publish(submission)
    assert entry.log_sequence == 900_001
    assert entry.submission_bytes == submission
    assert {:ok, retry, :existing} = NetworkFixture.publish(submission)
    assert retry.id == entry.id
    assert retry.receipt_bytes == entry.receipt_bytes
    assert [read] = Network.list_publication_entries!()
    assert read.id == entry.id
    assert read.submission_bytes == submission

    assert public_rows ==
             Repo.query!("SELECT count(*) FROM public.network_publication_entries").rows

    assert public_sequence ==
             Repo.query!("SELECT last_value, is_called FROM public.network_publication_sequence").rows
  end

  test "incomplete imported history stops before touching either migration ledger" do
    Repo.query!(
      "DELETE FROM techtree_app.schema_migrations WHERE version=(SELECT min(version) FROM techtree_app.schema_migrations)"
    )

    public = Repo.query!("SELECT version FROM public.schema_migrations ORDER BY version").rows

    selected =
      Repo.query!("SELECT version FROM techtree_app.schema_migrations ORDER BY version").rows

    assert_raise RuntimeError, ~r/Import the complete Techtree schema/, fn ->
      Techtree.Release.migrate()
    end

    assert public ==
             Repo.query!("SELECT version FROM public.schema_migrations ORDER BY version").rows

    assert selected ==
             Repo.query!("SELECT version FROM techtree_app.schema_migrations ORDER BY version").rows
  end
end
