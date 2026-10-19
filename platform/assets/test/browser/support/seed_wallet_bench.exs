# Recorded Wallet Bench tests for the browser tests (Techtree.WalletBenchFixture),
# seeded in the browser test database; prints each one's id and name by outcome.
unless Mix.env() == :test and
         String.starts_with?(System.get_env("MIX_TEST_PARTITION", ""), "browser"),
       do: raise("browser test database only")

Logger.configure(level: :warning)
{:ok, _} = Application.ensure_all_started([:postgrex, :ecto_sql, :ash, :ash_postgres])
{:ok, _} = Techtree.Repo.start_link()

Techtree.WalletBenchFixture.seed!()
|> Map.new(fn {outcome, attempt} ->
  {outcome, %{id: attempt.id, name: TechtreeWeb.WalletBenchCopy.pair(attempt)}}
end)
# Printed as ASCII: a script's output isn't written as UTF-8 (the names hold a ×).
|> Jason.encode!(escape: :unicode_safe)
|> IO.puts()
