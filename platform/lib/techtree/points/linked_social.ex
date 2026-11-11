defmodule Techtree.Points.LinkedSocial do
  @moduledoc """
  Regent Points' check of a linked social account: it reads the saved link and
  answers with what Points records. The provider and subject are the proof, so
  one social account earns once, whichever account links it; a link removed
  before the check earns nothing.

  `existing/2` lists the links to the rule's provider made before the Points
  start and still there, for `RegentPoints.StartAwards`.
  """

  alias Techtree.Accounts
  alias Techtree.Actors.System

  def verify(%{"source_event_key" => key}) do
    [provider, subject] = String.split(key, ":", parts: 2)

    case Accounts.get_linked_identity_by_subject(provider, subject, actor: %System{}) do
      {:ok, %{} = identity} -> {:ok, facts(identity, key)}
      {:ok, nil} -> {:error, :link_not_found}
      {:error, reason} -> {:retry, reason}
    end
  end

  def existing("social." <> provider, starts_at) do
    for identity <-
          Accounts.linked_identities_before!(provider, starts_at, actor: %System{}) do
      {identity.human_account_id,
       %{
         source_app: "regents",
         source_kind: "linked_identity",
         source_event_key: "#{identity.provider}:#{identity.subject}"
       }}
    end
  end

  defp facts(identity, key) do
    %{
      source_app: "regents",
      source_kind: "linked_identity",
      source_event_key: key,
      account_id: identity.human_account_id,
      actor_kind: "human",
      actor_id: to_string(identity.human_account_id),
      # When this subject was linked to the account; a later sign-in never moves it.
      source_action_at: identity.inserted_at,
      qualified_at: identity.inserted_at,
      evidence_ref: "linked_identity:" <> identity.id,
      evidence: %{"subject_key" => key}
    }
  end
end
