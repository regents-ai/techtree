# One agent paired with the signed-in visitor of sign_in.exs, under a name and
# wallet of its own, for a test that changes it; prints the agent's name.
unless Mix.env() == :test and
         String.starts_with?(System.get_env("MIX_TEST_PARTITION", ""), "browser"),
       do: raise("browser test database only")

Logger.configure(level: :warning)
{:ok, _} = Application.ensure_all_started([:postgrex, :ecto_sql, :ash, :ash_postgres])
{:ok, _} = Techtree.Repo.start_link()

suffix = 4 |> :crypto.strong_rand_bytes() |> Base.encode16(case: :lower)
name = "Walk Agent #{suffix}"

code = RegentAgents.issue_pairing_code!(actor: %RegentAgents.Person{privy_user_id: "did:privy:browser-test"})

RegentAgents.pair_agent!(code.code, name, :hermes,
  actor: %RegentAgents.Agent{wallet: "0x" <> String.duplicate(suffix, 5)}
)

IO.puts(Jason.encode!(%{name: name}))
