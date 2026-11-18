defmodule Mix.Tasks.Techtree.WalletBench do
  @shortdoc "Plan, start or inspect a wallet bench batch; read or correct one judge check"
  @moduledoc """
      mix techtree.wallet_bench plan --axis harness --id H16 --version 0.10.0 --operator sean --output prime.json
      mix techtree.wallet_bench plan --axis wallet --id W01 --version 0.3.45 --operator sean --output bankr.json
      mix techtree.wallet_bench validate --manifest prime.json
      mix techtree.wallet_bench start --manifest prime.json --execute
      mix techtree.wallet_bench status --batch UUID
      mix techtree.wallet_bench check --attempt UUID --test T2 --criterion C6
      mix techtree.wallet_bench correct --attempt UUID --test T2 --criterion C6 --value false --reason "..." --reviewer "Techtree review" --operator sean

  Plan and validate do not start the application, create jobs or call providers.
  Starting is an operator action: obtain approval for the reviewed manifest's
  paid provider calls first. For a deployed release, call
  Techtree.WalletBench.Batch.start(Jason.decode!(manifest_json)) by release RPC.
  Never pass secrets in the manifest. Only wallet tests are admitted, no funding.

  Check prints one of the judge's checks on a turn and only reads. Correct
  records a reviewer's correction to that one check (`--value` is true, false or
  open) with its own event on the attempt's timeline, and prints the check before
  and after; it calls no judge and spends nothing, and run again with the same
  value it changes nothing. For a deployed release, call
  Techtree.WalletBench.Correction.check/3 or correct/7 by release RPC.
  """

  use Mix.Task
  alias Techtree.WalletBench.{Batch, Correction}

  @commands "Use plan, validate, start, status, check or correct"

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
          attempt: :string,
          test: :string,
          criterion: :string,
          value: :string,
          reason: :string,
          reviewer: :string
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

      "check" ->
        Application.ensure_all_started(:ash_postgres)

        {:ok, result, _apps} =
          Ecto.Migrator.with_repo(Techtree.Repo, fn _repo ->
            Correction.check(
              Keyword.fetch!(options, :attempt),
              Keyword.fetch!(options, :test),
              Keyword.fetch!(options, :criterion)
            )
          end)

        result |> answer() |> print()

      "correct" ->
        # The site runs, so the correction reaches open pages as it would in production.
        Mix.Task.run("app.start")

        Correction.correct(
          Keyword.fetch!(options, :attempt),
          Keyword.fetch!(options, :test),
          Keyword.fetch!(options, :criterion),
          Keyword.fetch!(options, :value),
          Keyword.fetch!(options, :reason),
          Keyword.fetch!(options, :reviewer),
          Keyword.fetch!(options, :operator)
        )
        |> answer()
        |> print()

      _ ->
        Mix.raise(@commands)
    end
  end

  def run(_), do: Mix.raise(@commands)

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

  defp answer({:ok, value}), do: value
  defp answer({:error, message}), do: Mix.raise(message)

  defp print(value), do: Mix.shell().info(Jason.encode!(value, pretty: true))
end
