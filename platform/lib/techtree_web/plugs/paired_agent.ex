defmodule TechtreeWeb.Plugs.PairedAgent do
  @moduledoc "Current pairing for a SIWA-verified request; owner cookies grant no agent authority."
  @behaviour Plug
  import Plug.Conn
  alias TechtreeWeb.ExactResponse

  def init(opts), do: opts

  def call(conn, _opts) do
    conn =
      Siwa.AgentAuthPlug.call(conn,
        client: RegentAgents.Broker,
        hooks: RegentAgents.HTTP.Hooks,
        audience: RegentAgents.Broker.audience()
      )

    case conn.assigns do
      %{regent_agent: %RegentAgents.Agent{wallet: wallet}} -> pair(conn, wallet)
      %{regent_agent_refusal: refusal} -> refuse_proof(conn, refusal)
    end
  end

  defp pair(conn, wallet) do
    case RegentAgents.Authority.resolve(Techtree.Repo, wallet) do
      {:ok, pairing} ->
        account(conn, pairing)

      {:error, :not_paired} ->
        refuse(
          conn,
          403,
          :agent_not_paired,
          "This agent has no current account pairing.",
          "Ask the owner to pair this agent at regents.sh/account, then sign a fresh request."
        )

      {:error, _error} ->
        refuse(
          conn,
          503,
          :pairing_unavailable,
          "Current pairing could not be checked.",
          "Try again with a fresh signed request."
        )
    end
  end

  defp account(conn, pairing) do
    case Techtree.Accounts.by_owner(pairing.privy_user_id, actor: %{role: :system}) do
      {:ok, %{id: id}} ->
        assign(conn, :publication_actor, Map.put(pairing, :human_account_id, id))

      {:ok, nil} ->
        refuse(
          conn,
          403,
          :person_not_here,
          "The paired owner has no canonical Regent account.",
          "Ask the owner to sign in at regents.sh/account; no account was guessed or created."
        )

      {:error, _error} ->
        refuse(
          conn,
          503,
          :account_unavailable,
          "The canonical account could not be read.",
          "Try again with a fresh signed request."
        )
    end
  end

  defp refuse_proof(conn, %{siwa_status: status} = refusal) when status in 400..599 do
    refuse(
      conn,
      status,
      refusal[:siwa_code] || :sign_in_refused,
      refusal[:siwa_message] || "The request signature was refused.",
      refusal[:siwa_hint] || "Use https://siwa.regents.sh/skill.md to sign this exact request."
    )
  end

  defp refuse_proof(conn, refusal) do
    unavailable? = refusal[:reason] == :siwa_request_failed

    refuse(
      conn,
      if(unavailable?, do: 503, else: 401),
      refusal[:reason] || :sign_in_refused,
      if(unavailable?,
        do: "The sign-in service could not be reached.",
        else: "The exact request needs a valid agent signature."
      ),
      "Use https://siwa.regents.sh/skill.md to sign this exact request for Techtree."
    )
  end

  defp refuse(conn, status, code, message, hint) do
    conn |> ExactResponse.send_error(status, code, message, hint) |> halt()
  end
end
