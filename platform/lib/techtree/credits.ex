defmodule Techtree.Credits do
  @moduledoc """
  This site's part in Regent Credits (`RegentCredits`): the name it acts under
  and the actors it passes. The library keeps the balance; the site says who
  is asking, from what its own sign-in verified.
  """

  require Ash.Query

  alias RegentCredits.{Actor, Hold, Purchase}

  @doc "The signed-in account, with the wallets its sign-in verified."
  def person(account),
    do: Actor.person(account.privy_user_id, account.wallet_addresses, Techtree.site())

  @doc "The signed-in account as a Credits admin; the library's `:admins` setting decides if it is one."
  def admin(account), do: Actor.admin(account.privy_user_id)

  @doc """
  What the agent with this address has spent of the person's Credits on every
  Regent site: `{:ok, amount}`, nothing spent being zero.
  """
  def spent_by(person, agent_address) do
    address = String.downcase(agent_address)

    # The person's own holds, whatever else the actor may read.
    Hold
    |> Ash.Query.filter(agent_address == ^address and privy_user_id == ^person.privy_user_id)
    |> Ash.sum(:used, actor: person)
    |> case do
      {:ok, nil} -> {:ok, Decimal.new(0)}
      result -> result
    end
  end

  @doc "Saved Base purchase state for the person's displayed transactions; never reads the chain."
  def stored_purchases(account, hashes) do
    Purchase
    |> Ash.Query.filter(
      privy_user_id == ^account.privy_user_id and chain == :base and tx_hash in ^hashes
    )
    |> Ash.read(actor: person(account))
  end

  @doc "The site's own server code."
  def site_actor, do: Actor.site(Techtree.site())
end
