# A signed-in visitor for the browser tests: the person and wallet named on the
# command line (support/visitor.ts), with an account and profile in the browser
# test database and a session bound to it, printed as the cookie a browser would
# hold.
# Run from platform/ with the browser test server's environment.
unless Mix.env() == :test and String.starts_with?(System.get_env("MIX_TEST_PARTITION", ""), "browser"),
  do: raise("browser test database only")

[person, wallet] = System.argv()

{:ok, _} = Application.ensure_all_started([:postgrex, :ecto_sql, :ash, :ash_postgres])
{:ok, _} = Techtree.Repo.start_link()

%{rows: [[id]]} =
  Techtree.Repo.query!(
    """
    INSERT INTO regent_names.platform_human_users
      (privy_user_id, wallet_address, wallet_addresses, created_at, updated_at)
    VALUES ($1, $2, $3, now(), now())
    ON CONFLICT (privy_user_id) DO UPDATE SET updated_at = now()
    RETURNING id
    """,
    [person, wallet, [wallet]]
  )

# The person's shared profile, which a real sign-in makes (RegentIdentity.ensure/1),
# with no name, so every sign-in starts from the same page.
Techtree.Repo.query!(
  """
  INSERT INTO regent_identity.profiles
    (id, app_id, privy_user_id, wallet_addresses, proof_issued_at, inserted_at, updated_at)
  VALUES (gen_random_uuid(), $1, $2, $3, $4, now(), now())
  ON CONFLICT (app_id, privy_user_id) DO UPDATE SET display_name = NULL, updated_at = now()
  """,
  [Application.fetch_env!(:techtree, :privy)[:app_id], person, [wallet], System.system_time(:second)]
)

alias Techtree.Accounts.SessionAuthority
{:bootstrap, claim} = SessionAuthority.renew(nil)
{:ok, :bind, claim} = SessionAuthority.sign_in(claim, id)

endpoint = Application.fetch_env!(:techtree, TechtreeWeb.Endpoint)
options = Plug.Session.init(Application.fetch_env!(:techtree, :session_options))

conn =
  Plug.Test.conn(:get, "/")
  |> Map.put(:secret_key_base, endpoint[:secret_key_base])
  |> Plug.Session.call(options)
  |> Plug.Conn.fetch_session()
  |> then(&Enum.reduce(SessionAuthority.session(claim), &1, fn {k, v}, c -> Plug.Conn.put_session(c, k, v) end))
  |> Plug.Conn.send_resp(200, "")

{name, %{value: value}} = Enum.find(conn.resp_cookies, fn {_name, cookie} -> is_map(cookie) end)
IO.puts(Jason.encode!(%{name: name, value: value}))
