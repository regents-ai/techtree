defmodule Techtree.Accounts.SessionAuthorityTest do
  use Techtree.DataCase, async: true

  alias Techtree.Accounts.SessionAuthority

  @wallet "0x" <> String.duplicate("a", 40)

  setup do
    %{rows: [[id]]} =
      Repo.query!(
        """
        INSERT INTO regent_names.platform_human_users
          (privy_user_id, wallet_address, wallet_addresses, created_at, updated_at)
        VALUES ('did:privy:session-test', $1, $2, now(), now())
        RETURNING id
        """,
        [@wallet, [@wallet]]
      )

    account = %{id: id}

    {:bootstrap, claim} = SessionAuthority.renew(nil)
    {:ok, :bind, claim} = SessionAuthority.sign_in(claim, account.id)
    %{account: account, claim: claim}
  end

  test "a refresh keeps the sign-in's original end", %{account: account, claim: claim} do
    {lineage, _account, lapses_at} = SessionAuthority.resolve(claim)

    {:ok, :refresh, refreshed} = SessionAuthority.sign_in(claim, account.id)

    assert {^lineage, _account, ^lapses_at} = SessionAuthority.resolve(refreshed)
  end

  test "a sign-in refreshed every day still ends 30 days after it was made",
       %{account: account, claim: claim} do
    signed_in(claim, days_ago: 29)
    {:ok, :refresh, refreshed} = SessionAuthority.sign_in(claim, account.id)
    {_lineage, _account, lapses_at} = SessionAuthority.resolve(refreshed)
    assert DateTime.diff(lapses_at, DateTime.utc_now(), :hour) in 23..24

    signed_in(claim, days_ago: 31)

    assert SessionAuthority.resolve(refreshed) == {nil, nil, nil}
    assert SessionAuthority.sign_in(refreshed, account.id) == {:error, :reset}
  end

  defp signed_in(%{lineage: lineage}, days_ago: days) do
    digest = :crypto.hash(:sha256, lineage)
    at = DateTime.add(DateTime.utc_now(), -days * 86_400)

    {1, _rows} =
      Repo.update_all(from(s in SessionAuthority, where: s.lineage_digest == ^digest),
        set: [signed_in_at: at]
      )
  end
end
