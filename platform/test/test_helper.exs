ExUnit.start()

# The shared tables publication reads but Regents owns: the canonical account
# table, and the agent pairing schema from regent_agents' own migrations, which
# Regents alone runs in production. Running either again changes nothing.
__DIR__
|> Path.join("support/shared_tables.sql")
|> File.read!()
|> String.split(";\n", trim: true)
|> Enum.map(&String.trim/1)
|> Enum.reject(&(&1 == ""))
|> Enum.each(&Ecto.Adapters.SQL.query!(Techtree.Repo, &1, []))

RegentAgents.Migrator.up(Techtree.Repo)

Ecto.Adapters.SQL.Sandbox.mode(Techtree.Repo, :manual)

# The key this run of the suite countersigns receipts with. It is generated
# here, once, and exists only for as long as the beam does: there is no signing
# key anywhere in this repository, and a fixture holding one could be mistaken
# for a key somebody was meant to use. Tests that need a build with no key
# configured take this one away and put it back.
{_public, private} = :crypto.generate_key(:eddsa, :ed25519)
Application.put_env(:techtree, Techtree.Network.Key, private_key: Base.encode64(private))
