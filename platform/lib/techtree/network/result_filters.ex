defmodule Techtree.Network.ResultFilters do
  @moduledoc """
  The model, challenge and route an address narrows the Results to, each
  chosen among the values the coordinates before it leave.

  Every coordinate is optional, and one left out is every value of it, so an
  address that chooses nothing shows every Result. Unknown coordinates never
  broaden a query, and Campaign titles never serve as identities.
  """

  alias Techtree.Network.Query

  def empty, do: %{models: [], model: nil, challenges: [], challenge: nil, routes: [], route: nil}

  def select(selection, params) do
    {agent, version} = harness(selection)
    models = Query.result_models(agent, version)
    model = Map.get(params, "model")

    with true <- is_nil(model) or model in models,
         challenges = Query.result_challenges(agent, version, model),
         challenge = Map.get(params, "challenge"),
         true <-
           is_nil(challenge) or Enum.any?(challenges, &(&1.campaign_spec_digest == challenge)),
         routes = Query.result_routes(agent, version, model, challenge),
         route = Map.get(params, "route"),
         true <- is_nil(route) or route in routes do
      {:ok,
       %{
         models: models,
         model: model,
         challenges: challenges,
         challenge: challenge,
         routes: routes,
         route: route
       }}
    else
      false -> :error
    end
  end

  defp harness(nil), do: {nil, nil}
  defp harness(%{family: family, version: version}), do: {family.id, version}
end
