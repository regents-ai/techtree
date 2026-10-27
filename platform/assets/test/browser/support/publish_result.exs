# One published Result for the browser tests: the fixture catalog
# (Techtree.CatalogFixture) is written into the test server's own catalog folder
# (TECHTREE_CATALOG_ROOT, set by playwright.config.ts) and imported, and the
# fixture proof (Techtree.NetworkFixture) is published through the ingest.
# Prints the Result's fingerprint.
unless Mix.env() == :test and
         String.starts_with?(System.get_env("MIX_TEST_PARTITION", ""), "browser"),
       do: raise("browser test database only")

alias Techtree.NetworkFixture

Logger.configure(level: :warning)
{:ok, _} = Application.ensure_all_started([:postgrex, :ecto_sql, :ash, :ash_postgres, :req])
{:ok, _} = Techtree.Repo.start_link()

source = Path.expand("../../../../test/support/fixtures/catalog", __DIR__)
%{"techtree_python_revision" => revision} = source |> Path.join("source.json") |> File.read!() |> Jason.decode!()
bundle = Path.join([System.fetch_env!("TECHTREE_CATALOG_ROOT"), "sources", revision])
File.mkdir_p!(bundle)
File.cp_r!(source, bundle)
Techtree.Catalog.Importer.import!(bundle)

# Published as NetworkFixture.publish/2 does, with a countersigning key of this
# script's own (as test/test_helper.exs makes one) and the test server's address.
{_public, private} = :crypto.generate_key(:eddsa, :ed25519)
Application.put_env(:techtree, Techtree.Network.Key, private_key: Base.encode64(private))
{:ok, key} = Techtree.Network.Key.load()

{:ok, entry, :recorded} =
  NetworkFixture.scored()
  |> NetworkFixture.resign()
  |> NetworkFixture.submission()
  |> Techtree.Network.Ingest.accept(key,
    origin: "http://127.0.0.1:" <> System.fetch_env!("TECHTREE_BROWSER_PORT"),
    actor: NetworkFixture.paired_agent()
  )

IO.puts(Jason.encode!(%{digest: entry.bundle_digest}))
