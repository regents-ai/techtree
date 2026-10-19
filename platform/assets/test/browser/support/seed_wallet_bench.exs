# Recorded Wallet Bench tests for the browser tests (Techtree.WalletBenchFixture),
# seeded in the browser test database; prints their ids by outcome.
unless Mix.env() == :test and String.starts_with?(System.get_env("MIX_TEST_PARTITION", ""), "browser"),
  do: raise("browser test database only")

Logger.configure(level: :warning)
{:ok, _} = Application.ensure_all_started([:postgrex, :ecto_sql, :ash, :ash_postgres])
{:ok, _} = Techtree.Repo.start_link()

Techtree.WalletBenchFixture.seed!()
|> Map.new(fn {outcome, attempt} -> {outcome, attempt.id} end)
|> Jason.encode!()
|> IO.puts()
