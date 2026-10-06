defmodule TechtreeWeb.ModelAccess do
  @moduledoc """
  How pages name the routes a person runs a Climb on, and what each one needs.

  A Campaign offers one or more routes and the person picks one for each run.
  Every page reads the words from here, so the site names each route one way.
  """

  alias Techtree.Catalog.Route
  alias TechtreeWeb.Providers

  @names %{"prime_key" => "own Prime key", "chatgpt_plan" => "ChatGPT plan"}

  @needs %{
    "prime_key" =>
      "Your own Prime Intellect API key, set as PRIME_API_KEY or saved with prime login; " <>
        "the model calls are charged to your Prime account",
    "chatgpt_plan" =>
      "A ChatGPT Plus or Pro plan, signed in with regents techtree model login; the model " <>
        "calls use your plan's allowance"
  }

  @doc "A route's short name, as in \"Ran on: own Prime key\"."
  @spec name!(String.t()) :: String.t()
  def name!(route), do: Map.fetch!(@names, route)

  @doc "A route's name on its own, as a label: \"Own Prime key\"."
  @spec label!(String.t()) :: String.t()
  def label!(route) do
    {first, rest} = route |> name!() |> String.split_at(1)
    String.upcase(first) <> rest
  end

  @doc "The route a published Result ran on, named from the service its calls went to."
  @spec ran_on!(String.t()) :: String.t()
  def ran_on!(provider), do: provider |> Route.of_provider!() |> label!()

  @doc """
  Where a run's model calls go, over every route a Climb offers, as in "Prime
  Intellect on your own Prime key, or OpenAI on your ChatGPT plan".
  """
  @spec destinations([String.t(), ...]) :: String.t()
  def destinations(routes) do
    Enum.map_join(routes, ", or ", fn route ->
      Providers.name!(Route.provider!(route)) <> " on your " <> name!(route)
    end)
  end

  @doc "What a person needs to run on one route."
  @spec needs!(String.t()) :: String.t()
  def needs!(route), do: Map.fetch!(@needs, route)

  @doc """
  The prepare command for each route a Climb offers, each after a comment naming
  its route. `argv` is the command without its route.
  """
  @spec prepare_lines([String.t(), ...], [String.t()]) :: [{:comment | :command, term()}]
  def prepare_lines(routes, argv) do
    routes
    |> Enum.with_index()
    |> Enum.flat_map(fn {route, index} ->
      [
        {:comment, if(index == 0, do: "On your ", else: "Or on your ") <> name!(route) <> ":"},
        {:command, argv ++ ["--access", flag(route)]}
      ]
    end)
  end

  @doc "A run's dollar limit on the person's own Prime key, as in $6.50."
  @spec dollars(number()) :: String.t()
  def dollars(usd) when is_number(usd), do: "$" <> :erlang.float_to_binary(usd / 1, decimals: 2)

  defp flag(route), do: String.replace(route, "_", "-")
end
