defmodule Techtree.AccessContext.AccountControl do
  @moduledoc """
  Ash-owned shell view model for the account target. `squares` is the picture
  drawn from the account's wallet, there as soon as the page is; `picture` is
  its ENS name's picture, which arrives from another website and covers them.
  `ens_name` is the name its wallet's ENS record gives, shown as that wallet.
  """

  @enforce_keys [:kind, :label]
  defstruct @enforce_keys ++ [squares: nil, picture: nil, wallet: nil, ens_name: nil]
end
