defmodule Mix.Tasks.Techtree.Network.Seed do
  @shortdoc "Publish this project's own certification runs to the run log"

  @moduledoc """
  Put the certification runs on the run log, through the address every other
  publication goes through.

      $ mix techtree.network.seed --runs "$HOME/Library/Application Support/techtree/runs"

  `--runs` is the directory holding one subdirectory per run. It is named
  rather than guessed, because seeding a live log is an operator's decision and
  they should be looking at the path they are seeding from. The proof
  directories inside it are read and never written: a completed run's files are
  final.

  The task can be run again. The ingest is idempotent by bundle digest, so a
  second run sends the same bytes, gets the entry that is already there, and
  changes nothing.

  Two things have to be true of the database first: the catalog release these
  runs were produced against has been imported, because the log only accepts a
  run whose campaign this site publishes, and a signing key is configured,
  because this site countersigns every entry it accepts.
  """

  use Mix.Task

  alias Techtree.Network.Error
  alias Techtree.Network.Key
  alias Techtree.Network.Seed

  @impl Mix.Task
  def run(argv) do
    Mix.Task.run("app.start")

    {options, _rest} = OptionParser.parse!(argv, strict: [runs: :string])

    directory =
      Keyword.get_lazy(options, :runs, fn ->
        Mix.raise("name the directory holding the runs with --runs <path>")
      end)

    key =
      case Key.load() do
        {:ok, key} ->
          key

        :error ->
          Mix.raise(
            "this build holds no signing key, and every entry on the log is " <>
              "countersigned; set TECHTREE_NETWORK_SIGNING_KEY and try again"
          )
      end

    directory
    |> Seed.seed(key, TechtreeWeb.Endpoint.url())
    |> Enum.each(&report/1)
  end

  defp report({run_id, {:ok, sequence, :recorded}}),
    do: Mix.shell().info("#{run_id} published at log sequence #{sequence}")

  defp report({run_id, {:ok, sequence, :existing}}),
    do: Mix.shell().info("#{run_id} was already published at log sequence #{sequence}")

  defp report({run_id, {:error, :no_proof_directory}}),
    do: Mix.shell().error("#{run_id} has no proof directory under the directory given")

  defp report({run_id, {:error, %Error{} = error}}),
    do: Mix.shell().error("#{run_id} was refused: #{error.code} — #{error.message}")
end
