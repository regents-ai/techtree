defmodule Techtree.Repo.Migrations.WalletBenchRosterWebsites do
  @moduledoc """
  Two agents' websites in `wallet_bench_roster` (Sean, 13 October 2026, in the
  Patchbay thread: "deepseek's is https://www.deepseek.com and prime-agent's
  is https://www.primeintellect.ai/"). Both had only their repository on
  record. Patchbay names each agent's forum after its website's domain.

  The view keeps its columns; only the two addresses change.
  """

  use Ecto.Migration

  @websites [
    {"'https://github.com/deepseek-ai/deepseek-harness'", "'https://www.deepseek.com'"},
    {"'https://github.com/PrimeIntellect-ai/prime-agent'", "'https://www.primeintellect.ai/'"}
  ]

  def up, do: rewrite(@websites)

  def down, do: rewrite(Enum.map(@websites, fn {from, to} -> {to, from} end))

  defp rewrite(changes) do
    name = "#{Techtree.Repo.default_prefix()}.wallet_bench_roster"

    %{rows: [[current]]} =
      repo().query!("SELECT pg_get_viewdef($1::text::regclass, true)", [name])

    definition =
      Enum.reduce(changes, current, fn {from, to}, sql ->
        if not String.contains?(sql, from), do: raise("wallet_bench_roster does not say: #{from}")
        String.replace(sql, from, to)
      end)

    execute("CREATE OR REPLACE VIEW #{name} AS #{definition}")
  end
end
