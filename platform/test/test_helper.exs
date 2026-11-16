# As many tests at once as the test database has connections (config/test.exs):
# each test holds one, and a test left waiting in line for one is dropped once the
# pool's queue runs long, which on a busy machine fails it.
ExUnit.start(max_cases: Application.fetch_env!(:techtree, Techtree.Repo)[:pool_size])

Ecto.Adapters.SQL.Sandbox.mode(Techtree.Repo, :manual)

# The key this run of the suite countersigns receipts with. It is generated
# here, once, and exists only for as long as the beam does: there is no signing
# key anywhere in this repository, and a fixture holding one could be mistaken
# for a key somebody was meant to use. Tests that need a build with no key
# configured take this one away and put it back.
{_public, private} = :crypto.generate_key(:eddsa, :ed25519)
Application.put_env(:techtree, Techtree.Network.Key, private_key: Base.encode64(private))
