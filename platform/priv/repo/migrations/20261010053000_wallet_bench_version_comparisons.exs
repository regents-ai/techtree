defmodule Techtree.Repo.Migrations.WalletBenchVersionComparisons do
  @moduledoc "Append release context to existing results without replacing rows, run numbers, grants or dependent views."
  use Ecto.Migration

  def up do
    s = Techtree.Repo.default_prefix()

    execute(
      "CREATE TABLE #{s}.wallet_bench_version_view_backup (name text PRIMARY KEY, definition text NOT NULL)"
    )

    execute("""
    INSERT INTO #{s}.wallet_bench_version_view_backup (name, definition)
      SELECT name, rtrim(pg_get_viewdef((('#{s}.' || name)::regclass), true), E';\\n ')
      FROM (VALUES ('wallet_bench_results'), ('wallet_bench_roster')) saved(name);
    """)

    wrap_results(s, """
    prior.versions || CASE WHEN a.run_spec IS NOT NULL AND prior.grid IN ('wallet', 'install')
      THEN jsonb_build_object(
        'wallet', CASE WHEN CASE prior.grid WHEN 'install' THEN installed.wallet_verified
                      ELSE verified.wallet_verified END THEN a.run_spec->>'wallet_version' END,
        'wallet_verified', coalesce(CASE prior.grid WHEN 'install' THEN installed.wallet_verified
                                   ELSE verified.wallet_verified END, false)
      ) ELSE '{}'::jsonb END || jsonb_build_object(
      'batch', a.batch_id,
      'requested_wallet', a.run_spec->>'wallet_version',
      'protocol', a.run_spec->>'protocol',
      'access', a.run_spec->>'access'
    )
    """)

    execute("""
    DO $migration$
    DECLARE previous text;
    BEGIN
      SELECT rtrim(pg_get_viewdef('#{s}.wallet_bench_roster'::regclass, true), E';\\n ')
        INTO previous;
      EXECUTE 'CREATE OR REPLACE VIEW #{s}.wallet_bench_roster AS ' || previous ||
        ' UNION ALL SELECT ''harness''::text, ''H16''::text, ''Prime Agent''::text,
          (SELECT manifest->>''harness_version'' FROM #{s}.wallet_bench_machines
           WHERE harness_id = ''H16'' AND manifest IS NOT NULL ORDER BY inserted_at DESC LIMIT 1)';
    END $migration$;
    """)
  end

  def down do
    s = Techtree.Repo.default_prefix()

    execute("""
    DO $migration$
    DECLARE saved record;
    BEGIN
      FOR saved IN SELECT name, definition FROM #{s}.wallet_bench_version_view_backup LOOP
        EXECUTE 'CREATE OR REPLACE VIEW #{s}.' || saved.name || ' AS ' || saved.definition;
      END LOOP;
    END $migration$;
    """)

    execute("DROP TABLE #{s}.wallet_bench_version_view_backup")
  end

  defp wrap_results(s, versions) do
    execute("""
    DO $migration$
    DECLARE previous text;
    BEGIN
      SELECT rtrim(pg_get_viewdef('#{s}.wallet_bench_results'::regclass, true), E';\\n ')
        INTO previous;
      EXECUTE 'CREATE OR REPLACE VIEW #{s}.wallet_bench_results AS WITH prior AS (' || previous ||
        ') SELECT prior.harness_id, prior.wallet_id, prior.grid, prior.run, prior.outcome,
          prior.outcome_detail, prior.plain_file, prior.second_try, prior.signature_asked,
          prior.attempt_id, prior.run_url, #{String.replace(versions, "'", "''")} AS versions,
          prior.finished_at, prior.decided_by, prior.turns
          FROM prior JOIN #{s}.wallet_bench_attempts a ON a.id = prior.attempt_id
          LEFT JOIN LATERAL (
            SELECT bool_and(coalesce((t.checks->''version''->>''matches_requested'')::boolean, false))
              AS wallet_verified FROM #{s}.wallet_bench_turns t
            WHERE t.attempt_id = a.id AND t.test IN (''T2'', ''T2_signature'')
              AND t.judgment IS NOT NULL
          ) verified ON true
          LEFT JOIN LATERAL (
            SELECT (t.checks->''version''->>''matches_requested'')::boolean AS wallet_verified
            FROM #{s}.wallet_bench_turns t
            WHERE t.attempt_id = a.id AND t.test IN (''T1a'', ''T1b'')
              AND t.judgment IS NOT NULL AND t.checks ? ''version''
            ORDER BY t.inserted_at DESC LIMIT 1
          ) installed ON true';
    END $migration$;
    """)
  end
end
