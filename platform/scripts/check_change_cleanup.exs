# Only the databases created by scripts/check-change.py may be removed here.
run = System.fetch_env!("CHECK_CHANGE_RUN")

unless Mix.env() == :test and Regex.match?(~r/^_check_[0-9a-f]{12}$/, run),
  do: raise("check cleanup requires its own test run")

app = Mix.Project.config()[:app]

for repo <- Application.fetch_env!(app, :ecto_repos) do
  config = repo.config()
  database = Keyword.fetch!(config, :database)

  unless config[:hostname] in ["localhost", "127.0.0.1"] and
           config[:port] in [nil, 5432] and is_nil(config[:url]) and
           is_nil(config[:socket_dir]) and String.contains?(database, run) and
           String.contains?(database, "test") do
    raise "check cleanup refused a database outside its local test run"
  end

  # Regents' full gate also creates its independent identity test database.
  databases =
    if app == :regents,
      do: [database, "regent_identity_test" <> System.fetch_env!("MIX_TEST_PARTITION")],
      else: [database]

  for database <- databases do
    case repo.__adapter__().storage_down(Keyword.put(config, :database, database)) do
      :ok -> IO.puts("Removed check database #{database}")
      {:error, :already_down} -> :ok
      {:error, reason} -> raise "check database cleanup failed: #{inspect(reason)}"
    end
  end
end
