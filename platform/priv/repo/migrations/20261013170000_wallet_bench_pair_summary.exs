defmodule Techtree.Repo.Migrations.WalletBenchPairSummary do
  @moduledoc """
  `wallet_bench_pair_summary`: one row per comparable set of runs, read by
  Patchbay's board beside the five existing views (agreed with Patchbay,
  13 October 2026). It is the one definition of which runs may be counted
  together; nothing else groups runs.

  A set is every run of one agent, wallet and test that recorded the same
  context: everything in a result's `versions` except `batch`, which says where
  a run came from, not what it tested. The wallet release has one leading "v"
  removed and counts only when it is a release number (1.2.3, with an optional
  pre-release or build part) that the bench did not find to differ from the
  one asked for; `requested_wallet` is treated the same but keeps other text as
  written. A run whose wallet release is unknown cannot be shown to have tested
  the same release as any other, so it is a set of its own.

  - `set_id`: a digest of all of that, never NULL.
  - The twelve named context columns, and `other_versions` for any recorded
    field outside them; such a field still separates sets.
  - `current`: true on exactly one set per agent, wallet and test, the one that
    ran last (the lower `set_id` when two ended together).
  - `successes` counts PASS and PASS*; `caveat_runs` counts PASS* alone.
  - `proof_kind`: how a success on this test is established. The wallet test's
    signature is recovered by the bench and matched to the address; the refund
    and paid-picture tests are read from Base; everything else rests on the
    judge's reading of what the agent did.
  - `cost_per_success_usd` and `seconds_per_success`: all model and judge spend,
    and all time, of every run in the set on this test, successful or not,
    divided by the successes. NULL when there are none, and NULL when any turn
    in the set recorded no spend, or no time: an unknown figure is never shown
    as zero. A run with no turn on the test spent nothing.

  Every named context field on record is text or not recorded; a result with
  no recorded context at all is a set of its own with an empty
  `other_versions`.
  """

  use Ecto.Migration

  @named ~w(harness wallet model reasoning_effort os judge recipe protocol access requested_wallet setup hosted_model)
  @plain @named -- ~w(wallet requested_wallet)
  @pre "(0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
  @release "^(0|[1-9][0-9]*)[.](0|[1-9][0-9]*)[.](0|[1-9][0-9]*)(-#{@pre}([.]#{@pre})*)?([+][0-9A-Za-z-]+([.][0-9A-Za-z-]+)*)?$"

  def up do
    s = Techtree.Repo.default_prefix()

    execute("""
    CREATE VIEW #{s}.wallet_bench_pair_summary AS
    WITH runs AS (
      SELECT r.harness_id, r.wallet_id, r.grid, r.outcome, r.attempt_id, r.run_url, r.finished_at,
             (v.versions - 'batch') || jsonb_build_object(
               #{Enum.map_join(@plain, ", ", &"'#{&1}', nullif(v.versions->>'#{&1}', '')")},
               'wallet', CASE WHEN v.versions->'wallet_verified' IS DISTINCT FROM 'false'::jsonb
                              THEN release.wallet END,
               'requested_wallet', coalesce(release.requested_wallet, nullif(v.versions->>'requested_wallet', ''))
             ) AS versions,
             spend.cost_usd, spend.seconds
      FROM #{s}.wallet_bench_results r
      CROSS JOIN LATERAL (SELECT coalesce(r.versions, '{}'::jsonb) AS versions) v
      CROSS JOIN LATERAL (
        SELECT CASE WHEN bare.wallet ~ '#{@release}' THEN bare.wallet END AS wallet,
               CASE WHEN bare.requested_wallet ~ '#{@release}' THEN bare.requested_wallet END AS requested_wallet
        FROM (SELECT regexp_replace(v.versions->>'wallet', '^v', '') AS wallet,
                     regexp_replace(v.versions->>'requested_wallet', '^v', '') AS requested_wallet) bare
      ) release
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
      SELECT encode(sha256(convert_to(jsonb_build_array(grid, harness_id, wallet_id, versions, alone)::text, 'UTF8')), 'hex') AS set_id,
             harness_id, wallet_id, grid, versions,
             count(*)::integer AS runs,
             (count(*) FILTER (WHERE outcome IN ('PASS', 'PASS*')))::integer AS successes,
             (count(*) FILTER (WHERE outcome = 'PASS*'))::integer AS caveat_runs,
             CASE WHEN bool_and(cost_usd IS NOT NULL) THEN sum(cost_usd) END AS cost_usd,
             CASE WHEN bool_and(seconds IS NOT NULL) THEN sum(seconds) END AS seconds,
             max(finished_at) AS last_run_at,
             (array_agg(run_url ORDER BY finished_at DESC, attempt_id DESC))[1] AS latest_run_url
      FROM (SELECT runs.*, CASE WHEN versions->>'wallet' IS NULL THEN attempt_id END AS alone FROM runs) keyed
      GROUP BY harness_id, wallet_id, grid, versions, alone
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
  end

  def down do
    execute("DROP VIEW #{Techtree.Repo.default_prefix()}.wallet_bench_pair_summary")
  end
end
