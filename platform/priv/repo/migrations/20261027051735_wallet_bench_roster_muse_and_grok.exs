defmodule Techtree.Repo.Migrations.WalletBenchRosterMuseAndGrok do
  @moduledoc """
  Muse Code (H01) and Grok Build (H02) join `wallet_bench_roster` (Sean,
  27 October 2026: "1. a", add both to the live Agent Wallet Bench). Each row
  is shaped as the other agents' are: the version on the newest machine
  manifest for that agent, and the agent's own website, which Patchbay names
  its forum after.

  The view keeps its columns. Down leaves the two rows out again.
  """

  use Ecto.Migration

  @agents [
    {"H01", "Muse Code", "https://dev.meta.ai/products/muse-code"},
    {"H02", "Grok Build", "https://docs.x.ai/build/overview"}
  ]

  def up do
    s = Techtree.Repo.default_prefix()

    rows =
      Enum.map_join(@agents, ", ", fn {id, name, website} ->
        "('#{id}', '#{name}', '#{website}')"
      end)

    execute("""
    CREATE OR REPLACE VIEW #{s}.wallet_bench_roster AS
    #{definition(s)}
    UNION ALL
    SELECT 'harness'::text, agent.id, agent.name, (
      SELECT m.manifest->>'harness_version' FROM #{s}.wallet_bench_machines m
      WHERE m.harness_id = agent.id AND m.manifest IS NOT NULL ORDER BY m.inserted_at DESC LIMIT 1
    ), agent.website
    FROM (VALUES #{rows}) AS agent(id, name, website)
    """)
  end

  def down do
    s = Techtree.Repo.default_prefix()
    ids = Enum.map_join(@agents, ", ", fn {id, _name, _website} -> "'#{id}'" end)

    execute("""
    CREATE OR REPLACE VIEW #{s}.wallet_bench_roster AS
    SELECT * FROM (#{definition(s)}) roster WHERE roster.id NOT IN (#{ids})
    """)
  end

  defp definition(schema) do
    %{rows: [[definition]]} =
      repo().query!("SELECT rtrim(pg_get_viewdef($1::text::regclass, true), E';\\n ')", [
        "#{schema}.wallet_bench_roster"
      ])

    definition
  end
end
