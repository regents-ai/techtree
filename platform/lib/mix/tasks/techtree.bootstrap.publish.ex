defmodule Mix.Tasks.Techtree.Bootstrap.Publish do
  @shortdoc "Publish one staged bootstrap release, or roll back to a previous one"

  @moduledoc """
  Move the pointer that selects the installation contract this site publishes.

      $ mix techtree.bootstrap.publish --digest sha256:<64 hex>

  Releases are immutable and every one this channel ever imported stays staged,
  so rolling back is this same command naming the previous digest. Nothing is
  rewritten, nothing is deleted, and nothing already installed on anyone's
  machine is affected.

  `mix techtree.bootstrap.list` prints the digests to choose between.

  On a deployed release, where Mix is not available:

      $ bin/techtree eval 'Techtree.Release.publish_bootstrap("sha256:<64 hex>")'
  """

  use Mix.Task

  @impl Mix.Task
  def run(argv) do
    Mix.Task.run("app.start")

    {options, _rest} = OptionParser.parse!(argv, strict: [digest: :string, channel: :string])

    digest =
      Keyword.get_lazy(options, :digest, fn ->
        Mix.raise("name the release to publish with --digest sha256:<64 hex>")
      end)

    Techtree.Release.publish_bootstrap(digest, options[:channel])
  end
end
