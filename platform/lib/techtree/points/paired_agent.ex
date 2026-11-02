defmodule Techtree.Points.PairedAgent do
  @moduledoc """
  Regent Points' check of a pairing: it reads the pairing, kept after an
  unpair, and answers with what Points records for the person who made the
  pairing code.
  """

  alias Techtree.Accounts
  alias Techtree.Actors.System

  def verify(%{"source_event_key" => id}) do
    case RegentAgents.pairing_history(id) do
      {:ok, %{} = pairing} -> with_account(pairing)
      {:ok, nil} -> {:error, :pairing_not_found}
    end
  end

  defp with_account(pairing) do
    case Accounts.get_by_privy_did(pairing.privy_user_id, actor: %System{}) do
      {:ok, %{} = account} -> {:ok, facts(pairing, account)}
      {:ok, nil} -> {:error, :pairing_account_not_found}
      {:error, reason} -> {:retry, reason}
    end
  end

  defp facts(pairing, account) do
    %{
      source_app: "regents",
      source_kind: "pairing",
      source_event_key: pairing.id,
      account_id: account.id,
      actor_kind: "agent",
      # The agent's wallet, so the Points page names the agent the person paired.
      actor_id: pairing.wallet,
      source_action_at: pairing.paired_at,
      qualified_at: pairing.paired_at,
      evidence_ref: "pairing:" <> pairing.id,
      evidence: %{"attribution_link_id" => pairing.id}
    }
  end
end
