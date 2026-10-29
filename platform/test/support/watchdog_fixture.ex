defmodule Techtree.WatchdogFixture do
  @moduledoc """
  Helpers for Watchdog tests: a real signed-in person (a row in the shared
  accounts table, so the resources' foreign keys hold) and the actor that acts
  as them, plus a stub of the ownership check's requests through `Req.Test`.
  """

  alias Techtree.Actors.Human
  alias Techtree.Repo

  @doc "Makes a person and returns the `Human` actor that acts as them."
  def person!(suffix \\ nil) do
    suffix = suffix || Base.encode16(:crypto.strong_rand_bytes(6), case: :lower)
    wallet = "0x" <> Base.encode16(:crypto.strong_rand_bytes(20), case: :lower)

    %{rows: [[id]]} =
      Repo.query!(
        """
        INSERT INTO regent_names.platform_human_users
          (privy_user_id, wallet_address, wallet_addresses, created_at, updated_at)
        VALUES ($1, $2, $3, now(), now())
        RETURNING id
        """,
        ["did:privy:watchdog-#{suffix}", wallet, [wallet]]
      )

    %Human{human_account_id: id, name: "Watchdog #{suffix}", wallet_addresses: [wallet]}
  end

  @doc """
  Points the ownership check at `fun` for this test, so neither the real
  resolver nor any customer site is reached.
  """
  def stub_ownership(fun, resolver \\ fn _origin -> [{1, 1, 1, 1}] end) do
    Application.put_env(:techtree, Techtree.Watchdog.Ownership,
      req_options: [plug: {Req.Test, Techtree.Watchdog.Ownership}],
      resolver: resolver
    )

    Req.Test.stub(Techtree.Watchdog.Ownership, fun)
    :ok
  end

  @doc "A DNS-over-HTTPS JSON answer carrying the TXT values `records`."
  def dns_answer(records) do
    %{"Status" => 0, "Answer" => Enum.map(records, &%{"type" => 16, "data" => ~s("#{&1}")})}
  end
end
