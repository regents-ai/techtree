# Copy a generated CLI catalog export into the platform.
#
#     mix run scripts/sync_catalog.exs \
#       --source ../cli/src/techtree/resources/catalog \
#       --source-revision <full-commit> \
#       --generator-version <generator-version> \
#       --bootstrap path/to/bootstrap.json
#
# This is release engineering, not runtime behavior. The Python repository owns
# catalog generation; this script never generates anything scientific. It copies
# an export that already exists, writes the operational provenance beside it,
# verifies the raw bytes, and adds one immutable source snapshot.
#
# `--source-revision`, `--generator-version`, and `--bootstrap` are release
# inputs and are always supplied explicitly: the pinned CLI version and the
# pinned plugin commit are founder-owned decisions (spec section 4), and a
# provenance record this script guessed would be worth nothing.

alias Techtree.Catalog.Bundle
alias Techtree.Catalog.Digest
alias Techtree.Catalog.Error
alias Techtree.Catalog.Verifier

{options, _rest} =
  OptionParser.parse!(System.argv(),
    strict: [
      source: :string,
      destination: :string,
      source_revision: :string,
      generator_version: :string,
      bootstrap: :string
    ]
  )

required = [:source, :source_revision, :generator_version, :bootstrap]

case Enum.reject(required, &Keyword.has_key?(options, &1)) do
  [] ->
    :ok

  missing ->
    IO.puts(:stderr, "missing required options: " <> Enum.map_join(missing, ", ", &"--#{&1}"))
    System.halt(1)
end

source = Path.expand(options[:source])
root = Path.expand(Keyword.get(options, :destination, "priv/catalog"))
revision = options[:source_revision]

unless Regex.match?(~r/\A[0-9a-f]{40}\z/, revision) do
  raise Error.bundle_invalid("a catalog source revision must be 40 lowercase hex characters")
end

File.mkdir_p!(Path.join(root, "sources"))

destination =
  case Bundle.resolve(root, "sources") do
    {:ok, path} -> Path.join(path, revision)
    {:error, error} -> raise error
  end

unless File.lstat(destination) == {:error, :enoent} do
  raise Error.bundle_invalid("the source snapshot already exists; it will not be overwritten")
end

# Stage beside the destination so that the final move is a same-filesystem
# rename, and therefore atomic.
staging = destination <> ".staging-#{System.unique_integer([:positive])}"

File.mkdir_p!(Path.dirname(destination))
File.mkdir_p!(staging)
File.cp_r!(source, staging)
File.cp!(Path.expand(options[:bootstrap]), Path.join(staging, "bootstrap.json"))

catalog_bytes = File.read!(Path.join(staging, "catalog.json"))

provenance = %{
  "techtree_python_revision" => options[:source_revision],
  "catalog_digest" => Digest.hash_bytes(catalog_bytes),
  "generated_at" => DateTime.utc_now() |> DateTime.truncate(:second) |> DateTime.to_iso8601(),
  "generator_version" => options[:generator_version]
}

File.write!(Path.join(staging, "source.json"), Jason.encode!(provenance, pretty: true) <> "\n")

case Verifier.verify_bundle(Bundle.load!(staging)) do
  :ok ->
    :ok

  {:error, error} ->
    IO.puts(:stderr, Error.summary(error))
    IO.puts(:stderr, inspect(error.details))
    File.rm_rf!(staging)
    System.halt(1)
end

File.rename!(staging, destination)

IO.puts("synced #{destination}")
IO.puts("catalog #{provenance["catalog_digest"]}")
IO.puts("source revision #{provenance["techtree_python_revision"]}")
