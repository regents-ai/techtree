defmodule Techtree.Agents do
  @moduledoc """
  How an agent's check-in (`GET /api/agents/v1/me`) names the account it is
  paired with, including its verified wallet fields. This callback runs after
  the shared signed check-in; it is not a passive identity probe.
  """

  alias Techtree.Accounts
  alias Techtree.Actors.System

  def account(privy_user_id) do
    account = Accounts.get_by_privy_did!(privy_user_id, actor: %System{})

    %{
      display_name: account.display_name,
      ens_name: account.ens_name,
      wallet_address: account.wallet_address,
      wallet_addresses: account.wallet_addresses || []
    }
  end
end
