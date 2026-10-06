defmodule Techtree.Catalog.Route do
  @moduledoc """
  The routes a person runs a Climb on, and the service each one sends the
  model calls to.

  A Campaign offers one or more routes and a run uses one of them: the
  person's own Prime key, whose calls go to Prime, or their ChatGPT plan, whose
  calls go to OpenAI. The two go one to one, so a published Result keeps the
  service its calls went to and its route is read back from that.
  """

  @providers %{"prime_key" => "prime", "chatgpt_plan" => "openai"}
  @routes Map.new(@providers, fn {route, provider} -> {provider, route} end)

  @doc "The service a route's model calls go to."
  @spec provider!(String.t()) :: String.t()
  def provider!(route), do: Map.fetch!(@providers, route)

  @doc "The route a Result ran on, from the service its model calls went to."
  @spec of_provider!(String.t()) :: String.t()
  def of_provider!(provider), do: Map.fetch!(@routes, provider)

  @doc "Every route, in name order."
  @spec all() :: [String.t()]
  def all, do: @providers |> Map.keys() |> Enum.sort()
end
