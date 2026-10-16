defmodule Techtree.Actors.Operator do
  @moduledoc """
  A named person running the Wallet Bench from a console or a batch manifest.
  Operator actions run with policies skipped and record this name
  (`Techtree.WalletBench.Changes.Operator`).
  """

  @enforce_keys [:name]
  defstruct [:name]

  @type t :: %__MODULE__{name: String.t()}
end
