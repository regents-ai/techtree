defmodule Techtree.AccessContext do
  @moduledoc "Who a public shell page is rendered for: nobody, or a signed-in account."

  alias __MODULE__.AccountControl
  alias Techtree.PublicIdentity

  @enforce_keys [:principal]
  defstruct @enforce_keys

  @doc "The context for a signed-in account, or for nobody when there is none."
  def for_account(nil), do: %__MODULE__{principal: :anonymous}
  def for_account(account), do: %__MODULE__{principal: {:human, account}}

  @doc "The only wallets that may act for the account, lowercase and each once; `nil` signed out."
  def linked_wallets(%__MODULE__{principal: {:human, account}}),
    do: account.wallet_addresses |> Enum.map(&String.downcase/1) |> Enum.uniq()

  def linked_wallets(%__MODULE__{principal: :anonymous}), do: nil

  @doc "The account's own wallet, the one its sign-in verified, lowercase; `nil` signed out."
  def own_wallet(%__MODULE__{principal: {:human, %{wallet_address: address}}})
      when is_binary(address),
      do: String.downcase(address)

  def own_wallet(_context), do: nil

  def account_control(%__MODULE__{principal: :anonymous}),
    do: %AccountControl{kind: :sign_in, label: "Sign in"}

  def account_control(%__MODULE__{principal: {:human, account}} = context) do
    %AccountControl{
      kind: :signed_in,
      label: PublicIdentity.label(account),
      squares: PublicIdentity.squares(account),
      picture: PublicIdentity.picture(account),
      wallet: own_wallet(context)
    }
  end
end
