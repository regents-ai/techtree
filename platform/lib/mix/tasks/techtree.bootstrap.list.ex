defmodule Mix.Tasks.Techtree.Bootstrap.List do
  @shortdoc "List the bootstrap releases a channel has staged"

  @moduledoc """
  Print every installation contract this channel has imported, newest first,
  marking with `*` the one it publishes now.

      $ mix techtree.bootstrap.list

  This is where the two digests a rollback needs come from: the one being
  published, and the one to go back to.

  On a deployed release, where Mix is not available:

      $ bin/techtree eval 'Techtree.Release.list_bootstrap_releases()'
  """

  use Mix.Task

  @impl Mix.Task
  def run(argv) do
    Mix.Task.run("app.start")

    {options, _rest} = OptionParser.parse!(argv, strict: [channel: :string])

    Techtree.Release.list_bootstrap_releases(options[:channel])
  end
end
