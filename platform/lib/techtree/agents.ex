defmodule Techtree.Agents do
  @moduledoc """
  What an agent's check-in on this site says about its person's account.

  Techtree keeps no account for a person, so a paired agent's check-in carries
  the pairing and nothing more about them.
  """

  @doc "The account part of a check-in: empty, because this site keeps none."
  @spec account(String.t()) :: map()
  def account(_privy_user_id), do: %{}
end
