defmodule Techtree.Network.ResultFilters do
  @moduledoc """
  Dependent Result coordinates within a submitted harness version.

  Defaults use the most recently represented model, then its most recently
  represented exact Campaign. They are URL-pinned by the consumer, not treated
  as a claim about model release precedence. Unknown coordinates never broaden
  a query, and Campaign titles never serve as identities.
  """

  alias Techtree.Network.Query

  def empty, do: %{models: [], model: nil, challenges: [], challenge: nil}

  def select(nil, params) do
    if Map.has_key?(params, "model") or Map.has_key?(params, "challenge"),
      do: {:error, "No published Results match that model and challenge."},
      else: {:ok, empty()}
  end

  def select(selection, params) do
    models = Query.result_models(selection.family.id, selection.version)
    model = Map.get(params, "model", List.first(models))

    if model in models do
      challenges = Query.result_challenges(selection.family.id, selection.version, model)
      default = List.first(challenges)
      challenge = Map.get(params, "challenge", default && default.campaign_spec_digest)

      if Enum.any?(challenges, &(&1.campaign_spec_digest == challenge)) do
        {:ok, %{models: models, model: model, challenges: challenges, challenge: challenge}}
      else
        {:error, "No published Results match that challenge for this harness and model."}
      end
    else
      {:error, "No published Results match that model for this harness version."}
    end
  end
end
