defmodule Mix.Tasks.Techtree.Catalog.Import do
  @shortdoc "Import and activate a verified catalog bundle"

  @moduledoc """
  Import a generated catalog bundle and make it the active release.

      $ mix techtree.catalog.import --source-revision FULL_SOURCE_REVISION

  The bundle is verified before anything is written, and the whole import is one
  transaction: on any failure the previously active release keeps serving and
  the task exits nonzero.
  """

  use Mix.Task

  alias Techtree.Catalog.Error
  alias Techtree.Catalog.Importer

  @impl Mix.Task
  def run(argv) do
    Mix.Task.run("app.start")

    {options, _rest} =
      OptionParser.parse!(argv, strict: [source_revision: :string, channel: :string])

    import_options = Keyword.take(options, [:channel])

    try do
      root =
        case Techtree.Catalog.snapshot_path(options[:source_revision]) do
          {:ok, path} -> path
          {:error, error} -> raise error
        end

      release = Importer.import!(root, import_options)

      Mix.shell().info("""
      imported catalog #{release.catalog_digest}
      channel #{release.channel}
      source revision #{release.source_revision}
      """)
    rescue
      error in Error ->
        Mix.shell().error(Error.summary(error))
        exit({:shutdown, 1})
    end
  end
end
