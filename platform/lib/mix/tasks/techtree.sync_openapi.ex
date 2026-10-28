defmodule Mix.Tasks.Techtree.SyncOpenapi do
  @shortdoc "Writes cli/openapi.json from TechtreeWeb.OpenAPI"

  @moduledoc """
  Writes `cli/openapi.json`, the copy `make check-cli` reads, from
  `TechtreeWeb.OpenAPI`: the document https://techtree.sh serves, with the
  production request budget read from `config/config.exs` as `:prod` reads it.

      $ mix techtree.sync_openapi
      $ mix techtree.sync_openapi --check

  `--check` writes nothing and fails when the committed copy differs.
  """

  use Mix.Task

  @origin "https://techtree.sh"
  @config Path.expand("../../../config/config.exs", __DIR__)
  @target Path.expand("../../../../cli/openapi.json", __DIR__)

  @impl Mix.Task
  def run([]) do
    File.write!(@target, document())
    Mix.shell().info("Wrote cli/openapi.json")
  end

  def run(["--check"]) do
    if File.read!(@target) == document(),
      do: Mix.shell().info("cli/openapi.json is synchronized"),
      else: Mix.raise("cli/openapi.json is out of sync; run mix techtree.sync_openapi")
  end

  def run(_args), do: Mix.raise("usage: mix techtree.sync_openapi [--check]")

  defp document do
    Mix.Task.run("app.config")

    request_rate_limit =
      @config
      |> Config.Reader.read!(env: :prod, target: :host)
      |> Keyword.fetch!(:techtree)
      |> Keyword.fetch!(:request_rate_limit)

    Jason.encode!(TechtreeWeb.OpenAPI.document(@origin, request_rate_limit))
  end
end
