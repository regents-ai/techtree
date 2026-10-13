defmodule Techtree.Repo.Migrations.WalletBenchSetIdsAndWebsites do
  @moduledoc """
  Two additions Patchbay's board asked for (13 October 2026), each a last
  column on a view it already reads.

  `wallet_bench_results` gains `set_versions` and `set_id`: the context a run
  is counted under and the digest of it, worked out exactly as
  `wallet_bench_pair_summary` worked them out. The summary now groups on the
  `set_id` it reads from the results, so which runs may be counted together is
  defined once, on the run, and a reader that lists the runs of a set uses the
  same answer as the one that counts them. The summary's columns and rows do
  not change.

  `wallet_bench_roster` gains `website`: the address each agent and wallet
  publishes as its own home, or its repository where it publishes no other.
  NULL when the bench has none on record.

  There is no way down. Patchbay reads these columns, and a view cannot lose
  a column without being dropped. To go back, release the earlier image; it
  reads none of this.
  """

  use Ecto.Migration

  @named ~w(harness wallet model reasoning_effort os judge recipe protocol access requested_wallet setup hosted_model)
  @plain @named -- ~w(wallet requested_wallet)
  @pre "(0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
  @release "^(0|[1-9][0-9]*)[.](0|[1-9][0-9]*)[.](0|[1-9][0-9]*)(-#{@pre}([.]#{@pre})*)?([+][0-9A-Za-z-]+([.][0-9A-Za-z-]+)*)?$"

  @websites [
    {"H04", "https://hermes-agent.nousresearch.com"},
    {"H05", "https://claude.com/product/claude-code"},
    {"H06", "https://cline.bot"},
    {"H07", "https://kilo.ai"},
    {"H08", "https://pi.dev"},
    {"H09", "https://omp.sh"},
    {"H10", "https://openai.com/codex"},
    {"H12", "https://github.com/deepseek-ai/deepseek-harness"},
    {"H13", "https://opencode.ai"},
    {"H16", "https://github.com/PrimeIntellect-ai/prime-agent"},
    {"W01", "https://bankr.bot"},
    {"W02", "https://metamask.io"},
    {"W03", "https://www.moonpay.com/agents"},
    {"W05", "https://www.coinbase.com/developer-platform"},
    {"W06", "https://phantom.com"},
    {"W07", "https://www.getfoundry.sh"},
    {"W09", "https://www.circle.com"},
    {"W10", "https://safe.global"},
    {"W13", "https://zerion.io"},
    {"W14", "https://splits.org"},
    {"W15", "https://www.privy.io"},
    {"W17", "https://www.turnkey.com"}
  ]

  def up do
    s = Techtree.Repo.default_prefix()
    results = definition(s, "wallet_bench_results")
    roster = definition(s, "wallet_bench_roster")

    execute("""
    CREATE OR REPLACE VIEW #{s}.wallet_bench_results AS
    WITH prior AS (#{results})
    SELECT prior.harness_id, prior.wallet_id, prior.grid, prior.run, prior.outcome,
           prior.outcome_detail, prior.plain_file, prior.second_try, prior.signature_asked,
           prior.attempt_id, prior.run_url, prior.versions, prior.finished_at, prior.decided_by,
           prior.turns, keyed.set_versions,
           encode(sha256(convert_to(jsonb_build_array(
             prior.grid, prior.harness_id, prior.wallet_id, keyed.set_versions,
             CASE WHEN keyed.set_versions->>'wallet' IS NULL THEN prior.attempt_id END
           )::text, 'UTF8')), 'hex') AS set_id
    FROM prior
    CROSS JOIN LATERAL (SELECT coalesce(prior.versions, '{}'::jsonb) AS versions) v
    CROSS JOIN LATERAL (
      SELECT CASE WHEN bare.wallet ~ '#{@release}' THEN bare.wallet END AS wallet,
             CASE WHEN bare.requested_wallet ~ '#{@release}' THEN bare.requested_wallet END AS requested_wallet
      FROM (SELECT regexp_replace(v.versions->>'wallet', '^v', '') AS wallet,
                   regexp_replace(v.versions->>'requested_wallet', '^v', '') AS requested_wallet) bare
    ) release
    CROSS JOIN LATERAL (
      SELECT (v.versions - 'batch') || jsonb_build_object(
               #{Enum.map_join(@plain, ", ", &"'#{&1}', nullif(v.versions->>'#{&1}', '')")},
               'wallet', CASE WHEN v.versions->'wallet_verified' IS DISTINCT FROM 'false'::jsonb
                              THEN release.wallet END,
               'requested_wallet', coalesce(release.requested_wallet, nullif(v.versions->>'requested_wallet', ''))
             ) AS set_versions
    ) keyed
    """)

    execute("""
    CREATE OR REPLACE VIEW #{s}.wallet_bench_pair_summary AS
    WITH runs AS (
      SELECT r.set_id, r.harness_id, r.wallet_id, r.grid, r.outcome, r.attempt_id, r.run_url,
             r.finished_at, r.set_versions AS versions, spend.cost_usd, spend.seconds
      FROM #{s}.wallet_bench_results r
      CROSS JOIN LATERAL (
        SELECT CASE WHEN bool_or(t.model_spend_usd IS NULL AND t.judge_cost_usd IS NULL) THEN NULL
                    ELSE coalesce(sum(coalesce(t.model_spend_usd, 0) + coalesce(t.judge_cost_usd, 0)), 0)
               END AS cost_usd,
               CASE WHEN bool_or(t.wall_seconds IS NULL) THEN NULL ELSE coalesce(sum(t.wall_seconds), 0) END AS seconds
        FROM #{s}.wallet_bench_turns t
        WHERE t.attempt_id = r.attempt_id AND t.test = ANY (CASE r.grid
          WHEN 'install' THEN ARRAY['T1a', 'T1b']
          WHEN 'wallet' THEN ARRAY['T2', 'T2_signature']
          WHEN 'refund' THEN ARRAY['T3']
          WHEN 'image' THEN ARRAY['T4']
          WHEN 'patchbay' THEN ARRAY['T5']
        END)
      ) spend
    ),
    sets AS (
      SELECT set_id, harness_id, wallet_id, grid, versions,
             count(*)::integer AS runs,
             (count(*) FILTER (WHERE outcome IN ('PASS', 'PASS*')))::integer AS successes,
             (count(*) FILTER (WHERE outcome = 'PASS*'))::integer AS caveat_runs,
             CASE WHEN bool_and(cost_usd IS NOT NULL) THEN sum(cost_usd) END AS cost_usd,
             CASE WHEN bool_and(seconds IS NOT NULL) THEN sum(seconds) END AS seconds,
             max(finished_at) AS last_run_at,
             (array_agg(run_url ORDER BY finished_at DESC, attempt_id DESC))[1] AS latest_run_url
      FROM runs
      GROUP BY set_id, harness_id, wallet_id, grid, versions
    )
    SELECT set_id, harness_id, wallet_id, grid,
           versions->>'harness' AS harness_version,
           versions->>'wallet' AS wallet_version,
           #{Enum.map_join(@named -- ~w(harness wallet), ", ", &"versions->>'#{&1}' AS #{&1}")},
           versions - ARRAY[#{Enum.map_join(@named, ", ", &"'#{&1}'")}] AS other_versions,
           row_number() OVER (PARTITION BY harness_id, wallet_id, grid ORDER BY last_run_at DESC, set_id) = 1 AS current,
           runs, successes, caveat_runs,
           CASE grid
             WHEN 'wallet' THEN 'signature_checked'
             WHEN 'refund' THEN 'payment_read_from_base'
             WHEN 'image' THEN 'payment_read_from_base'
             ELSE 'judge_only'
           END AS proof_kind,
           CASE WHEN successes > 0 THEN round(cost_usd / successes, 4) END AS cost_per_success_usd,
           CASE WHEN successes > 0 THEN round(seconds / successes, 1) END AS seconds_per_success,
           last_run_at, latest_run_url
    FROM sets
    """)

    execute("""
    CREATE OR REPLACE VIEW #{s}.wallet_bench_roster AS
    WITH prior AS (#{roster})
    SELECT prior.kind, prior.id, prior.name, prior.version, site.website
    FROM prior
    LEFT JOIN (VALUES #{Enum.map_join(@websites, ", ", fn {id, website} -> "('#{id}', '#{website}')" end)})
      AS site(id, website) ON site.id = prior.id
    """)
  end

  def down do
    raise Ecto.MigrationError,
      message:
        "Patchbay reads the columns this migration added. Release the earlier image instead."
  end

  defp definition(schema, view) do
    %{rows: [[definition]]} =
      repo().query!("SELECT rtrim(pg_get_viewdef($1::text::regclass, true), E';\\n ')", [
        "#{schema}.#{view}"
      ])

    definition
  end
end
