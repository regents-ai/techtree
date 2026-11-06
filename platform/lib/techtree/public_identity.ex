defmodule Techtree.PublicIdentity do
  @moduledoc """
  The public name and picture of a signed-in account.

  The name is its display name or its wallet's ENS name, whichever the site's
  `:name_first` setting puts first (`:chosen` or `:ens`), else the other, else
  its shortened wallet address. Its squares are a picture generated from its
  wallet address; its picture is its ENS name's, when it has one. Every wallet is
  public, and so is the ENS name that points to it.
  """

  @wallet ~r/\A0x[0-9a-fA-F]{40}\z/

  @name_fields (case Application.compile_env!(:techtree, :name_first) do
                  :chosen -> [:display_name, :ens_name]
                  :ens -> [:ens_name, :display_name]
                end)

  def label(account),
    do:
      Enum.find_value(@name_fields, &present(Map.get(account, &1))) ||
        short_wallet(Map.get(account, :wallet_address))

  @doc """
  The name a list other people read prints for an account: its display name when
  that is the name it shows, else `nil` when it shows by its wallet, its ENS name
  or short address, which a page draws with `Regent.Primitives.address`. An account
  with neither a display name nor a wallet prints its `label/1`.
  """
  def listed_name(account) do
    case Enum.find(@name_fields, &present(Map.get(account, &1))) do
      :display_name -> present(account.display_name)
      _ -> if !wallet(account), do: label(account)
    end
  end

  @doc "The account's wallet address, when it has one."
  def wallet(account) do
    case Map.get(account, :wallet_address) do
      wallet when is_binary(wallet) ->
        wallet = String.trim(wallet)
        if Regex.match?(@wallet, wallet), do: wallet

      _ ->
        nil
    end
  end

  def picture(account), do: present(Map.get(account, :ens_avatar_url))

  def ens_name(account), do: present(Map.get(account, :ens_name))

  def squares(account), do: account |> wallet() |> identicon()

  defp short_wallet(wallet) when is_binary(wallet) do
    if Regex.match?(@wallet, wallet), do: RegentFormat.short_address(wallet), else: "Account"
  end

  defp short_wallet(_wallet), do: "Account"

  defp present(value) when is_binary(value) do
    case String.trim(value) do
      "" -> nil
      value -> value
    end
  end

  defp present(_value), do: nil

  # A 5×5 identicon mirrored around its middle column, coloured from the hash.
  defp identicon(nil), do: nil

  defp identicon(wallet) do
    <<red, green, blue, red2, green2, blue2, cells::binary>> =
      :crypto.hash(:sha256, String.downcase(wallet))

    primary = color(red, green, blue)
    secondary = color(red2, green2, blue2)

    marks =
      for {value, index} <- cells |> :binary.bin_to_list() |> Enum.take(15) |> Enum.with_index(),
          rem(value, 3) != 0,
          column <- mirrored_columns(rem(index, 3)) do
        fill = if rem(value, 3) == 1, do: primary, else: secondary
        ~s(<rect x="#{column}" y="#{div(index, 3)}" width="1" height="1" fill="#{fill}"/>)
      end

    svg =
      ~s(<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 5 5" shape-rendering="crispEdges"><rect width="5" height="5" fill="#121212"/>#{Enum.join(marks)}</svg>)

    "data:image/svg+xml;base64," <> Base.encode64(svg)
  end

  defp mirrored_columns(0), do: [0, 4]
  defp mirrored_columns(1), do: [1, 3]
  defp mirrored_columns(2), do: [2]

  defp color(red, green, blue), do: "rgb(#{bright(red)},#{bright(green)},#{bright(blue)})"

  defp bright(component), do: 72 + rem(component, 168)
end
