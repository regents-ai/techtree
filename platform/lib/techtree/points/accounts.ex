defmodule Techtree.Points.Accounts do
  @moduledoc "Verified account lookups supplied to the shared Points package."
  @behaviour RegentPoints.Accounts

  require Ash.Query

  alias Techtree.Accounts
  alias Techtree.Accounts.HumanAccount
  alias Techtree.Actors.System
  alias Techtree.PublicIdentity

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

  # What the board shows of each account: its name or wallet, and its pictures.
  @impl true
  def people([]), do: {:ok, %{}}

  def people(ids) do
    query =
      HumanAccount
      |> Ash.Query.filter(id in ^ids)
      |> Ash.Query.load([:display_name, :ens_name, :ens_avatar_url])

    with {:ok, accounts} <- Ash.read(query, actor: %System{}) do
      {:ok,
       Map.new(accounts, fn account ->
         {account.id,
          %{
            name: PublicIdentity.listed_name(account),
            wallet: PublicIdentity.wallet(account),
            ens_name: PublicIdentity.ens_name(account),
            squares: PublicIdentity.squares(account),
            picture: PublicIdentity.picture(account)
          }}
       end)}
    end
  end
end
