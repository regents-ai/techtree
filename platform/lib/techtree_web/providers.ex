defmodule TechtreeWeb.Providers do
  @moduledoc """
  The names a reader knows model providers by.

  A Campaign names its provider by the short identifier the command line uses.
  Pages show the provider's own name instead, and every page reads it from
  here, so the site spells each provider one way.
  """

  @names %{"prime" => "Prime Intellect"}

  @doc """
  The name a reader knows one provider by. A provider this site cannot name is
  a catalog this build was not made for, and raises.
  """
  @spec name!(String.t()) :: String.t()
  def name!(provider), do: Map.fetch!(@names, provider)
end
