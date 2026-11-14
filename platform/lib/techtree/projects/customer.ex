defmodule Techtree.Projects.Customer do
  @moduledoc """
  Finds the account a project is delivered to from what the team knows of the
  customer: a wallet the account signed in with, in any case, or the
  account's Privy id. The customer must have signed in here once. Techtree
  keeps no email address for an account, so the team finds the Privy id for
  an email in Privy's dashboard.
  """

  alias Techtree.Accounts
  alias Techtree.Actors.System

  @wallet ~r/\A0x[0-9a-fA-F]{40}\z/
  @privy_id ~r/\Adid:privy:[0-9A-Za-z_-]+\z/

  @doc "The account `customer` names, with its display name, or `nil` when none does."
  @spec find(String.t()) :: {:ok, Ash.Resource.record() | nil} | {:error, term()}
  def find(customer) do
    customer = String.trim(customer)

    cond do
      customer =~ @wallet ->
        Accounts.get_by_wallet(String.downcase(customer), actor: %System{})

      customer =~ @privy_id ->
        Accounts.get_by_privy_did(customer, actor: %System{})

      true ->
        {:ok, nil}
    end
  end
end
