defmodule Mix.Tasks.Techtree.Catalog.Verify do
  @shortdoc "Verify a generated catalog bundle without touching the database"

  @moduledoc """
  Load and verify a generated catalog bundle.

      $ mix techtree.catalog.verify --path priv/catalog

  Nothing is written. The task exits nonzero on the first failure, naming the
  error code from the spec section 15 taxonomy.
  """

  use Mix.Task

  alias Techtree.Catalog.Bundle
  alias Techtree.Catalog.Error
  alias Techtree.Catalog.Verifier

  @impl Mix.Task
  def run(argv) do
    Mix.Task.run("app.config")

    {options, _rest} = OptionParser.parse!(argv, strict: [path: :string])
    root = Keyword.get_lazy(options, :path, &Techtree.Catalog.catalog_root/0)

    try do
      bundle = Bundle.load!(root)
      Verifier.verify_bundle!(bundle)

      entries = Bundle.list_entries(bundle)
      climbs = Enum.count(entries, &(&1.kind == :climb))

      Mix.shell().info("""
      catalog #{Bundle.catalog_digest(bundle)}
      bootstrap #{Bundle.bootstrap_digest(bundle)}
      source revision #{Bundle.source_revision(bundle)}
      #{length(entries)} objects, #{climbs} public Climbs
      verified
      """)
    rescue
      error in Error ->
        Mix.shell().error(Error.summary(error))
        exit({:shutdown, 1})
    end
  end
end
