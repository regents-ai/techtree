defmodule Techtree.OAuth do
  @moduledoc """
  Consent for connected apps, such as Claude's connector, through the person's
  verified account. The identity permission lets the app keep an identity, pair
  it with this account and check in through the MCP address at `/mcp`; the
  agent permission (`agent_scope/0`) lets it then work here as that paired
  agent, with that agent's rights and nothing more.
  """
  @behaviour RegentOAuth

  alias Techtree.Accounts.VerifiedSession

  def config, do: Application.fetch_env!(:techtree, __MODULE__)

  @doc "The permission to work here as the paired agent, beside the identity one."
  def agent_scope, do: "techtree.agent"
  def repo, do: Techtree.Repo

  @doc """
  Whether the Claude connector is switched on (`TECHTREE_CLAUDE_CONNECTOR_ENABLED`,
  read once at boot): its sign-in, a connected app's token at `/mcp`, Claude in
  the pairing box and the Claude guide all follow this one setting.
  """
  def enabled?, do: Keyword.fetch!(config(), :enabled?)

  def current_subject(conn) do
    case conn.assigns[:current_human_account] do
      %{privy_user_id: subject} = account ->
        if VerifiedSession.current?(account), do: subject

      _ ->
        nil
    end
  end

  def active_subject?(subject) do
    case Techtree.Accounts.get_by_privy_did(subject, actor: %Techtree.Actors.System{}) do
      {:ok, account} -> VerifiedSession.current?(account)
      {:error, error} -> raise error
    end
  end
end
