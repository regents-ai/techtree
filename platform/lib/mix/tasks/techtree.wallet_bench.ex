defmodule Mix.Tasks.Techtree.WalletBench do
  @shortdoc "Plan, manually start, or inspect an exact-version wallet bench batch"
  @moduledoc """
      mix techtree.wallet_bench plan --axis harness --id H16 --version 0.10.0 --operator sean --output prime.json
      mix techtree.wallet_bench plan --axis wallet --id W01 --version 0.3.45 --operator sean --output bankr.json
      mix techtree.wallet_bench plan --axis pair --id H05-W01 --repeats 3 --model-budget-usd 1 \
        --skill wallet-secrets --operator sean --output skill.json
      mix techtree.wallet_bench validate --manifest prime.json
      mix techtree.wallet_bench start --manifest prime.json --execute
      mix techtree.wallet_bench status --batch UUID

  A pair runs one agent and one wallet tool at their default releases. `--skill`
  installs one of Techtree's own Skills in the agent before its first turn; the
  manifest names it and its sha256. `--model-budget-usd` is the most each
  attempt's model calls may cost (5 unless given); the judge's calls are extra.

  Plan and validate do not start the application, create jobs or call providers.
  Starting is an operator action: obtain approval for the reviewed manifest's
  paid provider calls first. For a deployed release, call
  Techtree.WalletBench.Batch.start(Jason.decode!(manifest_json)) by release RPC.
  Never pass secrets in the manifest. Only wallet tests are admitted, no funding.
  """

  use Mix.Task
  alias Techtree.WalletBench.Batch

  @impl true
  def run([command | args]) do
    Mix.Task.run("app.config")

    {options, rest} =
      OptionParser.parse!(args,
        strict: [
          axis: :string,
          id: :string,
          version: :string,
          operator: :string,
          source_ref: :string,
          archive_sha256: :string,
          integrity: :string,
          repeats: :integer,
          output: :string,
          manifest: :string,
          execute: :boolean,
          batch: :string,
          skill: :string,
          model_budget_usd: :float
        ]
      )

    if rest != [], do: Mix.raise("Unexpected positional arguments")

    case command do
      "plan" ->
        manifest = Batch.plan(options)

        File.write!(
          Keyword.fetch!(options, :output),
          Jason.encode!(manifest, pretty: true) <> "\n"
        )

        print(Batch.summary(manifest))

      "validate" ->
        print(Batch.summary(manifest(options)))

      "start" ->
        start(options)

      "status" ->
        Application.ensure_all_started(:ash_postgres)

        {:ok, result, _apps} =
          Ecto.Migrator.with_repo(Techtree.Repo, fn _repo ->
            Batch.status(Keyword.fetch!(options, :batch))
          end)

        print(result)

      _ ->
        Mix.raise("Use plan, validate, start or status")
    end
  end

  def run(_), do: Mix.raise("Use plan, validate, start or status")

  defp start(options) do
    planned = manifest(options)

    if options[:execute] != true,
      do: Mix.raise("Review the manifest and its spending before passing --execute")

    Mix.Task.run("app.start")

    case Batch.start(planned) do
      {:ok, attempts} ->
        print(%{batch: planned["batch"], attempts: Enum.map(attempts, & &1.id)})

      {:error, reason} ->
        Mix.raise("Batch admission failed: #{inspect(reason)}")
    end
  end

  defp manifest(options),
    do:
      options |> Keyword.fetch!(:manifest) |> File.read!() |> Jason.decode!() |> Batch.validate!()

  defp print(value), do: Mix.shell().info(Jason.encode!(value, pretty: true))
end
