defmodule Techtree.Network.ResultFilters do
  @moduledoc """
  Dependent Result coordinates within a submitted harness version.

  Defaults use the most recently represented model, then its most recently
  represented exact Campaign. The route is the one coordinate without a
  default: every route's Results show together until one is chosen. They are URL-pinned by the consumer, not treated
  as a claim about model release precedence. Unknown coordinates never broaden
  a query, and Campaign titles never serve as identities.
  """

  alias Techtree.Network.Query

  def empty, do: %{models: [], model: nil, challenges: [], challenge: nil, routes: [], route: nil}

  def select(nil, params) do
    if Enum.any?(~w(model challenge route), &Map.has_key?(params, &1)),
      do: :error,
      else: {:ok, empty()}
  end

  def select(selection, params) do
    models = Query.result_models(selection.family.id, selection.version)
    model = Map.get(params, "model", List.first(models))

    with true <- model in models,
         challenges = Query.result_challenges(selection.family.id, selection.version, model),
         challenge = Map.get(params, "challenge", default_challenge(challenges)),
         true <- Enum.any?(challenges, &(&1.campaign_spec_digest == challenge)),
         routes = Query.result_routes(selection.family.id, selection.version, model, challenge),
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

  defp default_challenge([newest | _older]), do: newest.campaign_spec_digest
  defp default_challenge([]), do: nil
end
