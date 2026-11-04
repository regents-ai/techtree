defmodule Techtree.Points.Accounts do
  @moduledoc "Verified account lookups supplied to the shared Points package."
  @behaviour RegentPoints.Accounts

  alias Techtree.Accounts
  alias Techtree.Actors.System

  @impl true
  def human(id), do: Accounts.points_account!(id, actor: %System{})

  @impl true
  def agent_names(_id, []), do: {:ok, %{}}

  def agent_names(id, wallets) do
    # The canonical account supplies the owner; a wallet's newest pairing names it.
    with {:ok, account} <- Accounts.points_account(id, actor: %System{}),
         {:ok, pairings} <- RegentAgents.pairing_histories(account.privy_user_id) do
      names = for %{wallet: wallet, name: name} <- pairings, wallet in wallets, do: {wallet, name}
      {:ok, Map.new(names)}
    end
  end
end
