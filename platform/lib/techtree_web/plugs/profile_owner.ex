defmodule TechtreeWeb.Plugs.ProfileOwner do
  @moduledoc """
  Puts the profile's owner on a profile API request (`RegentIdentity.HTTP`): the
  person signed in on this site, or the person a paired agent acts for.

  An agent's signed request (`TechtreeWeb.Plugs.AgentWallet`) acts as its person
  while it is paired with them, and is refused as at every other paired-agent
  address otherwise. Any other request is the person's session cookie; a request
  that changes something carries the session's forms token in x-csrf-token, as
  the site's pages send it, and one without it counts as signed out, so another
  site's page can never act with the person's cookie. A signed-out request gets
  no owner, and the profile API refuses it with `authentication_required`.
  """

  @behaviour Plug

  import Plug.Conn

  alias Techtree.Actors.Agent
  alias TechtreeWeb.{ExactResponse, PrivySessionController}
  alias TechtreeWeb.Plugs.AgentWallet

  @forms_token Plug.CSRFProtection.init(with: :clear_session)

  @impl true
  def init(opts), do: opts

  @impl true
  def call(conn, _opts) do
    if Siwa.AgentAuthPlug.signed_request?(conn), do: agent(conn), else: person(conn)
  end

  defp agent(conn) do
    case AgentWallet.call(conn, []) do
      %{halted: true} = conn -> conn
      %{assigns: %{actor: %Agent{pairing: :active} = agent}} = conn -> owner(conn, agent)
      %{assigns: %{actor: agent}} = conn -> refuse(conn, AgentWallet.not_person_code(agent))
    end
  end

  defp person(conn) do
    conn =
      conn
      |> fetch_session()
      |> Plug.CSRFProtection.call(@forms_token)
      |> PrivySessionController.enforce_authority(:account)

    case conn.assigns.current_human_account do
      %{} = account -> owner(conn, account)
      nil -> conn
    end
  end

  defp owner(conn, %{privy_user_id: privy_user_id}) do
    app_id = :techtree |> Application.fetch_env!(:privy) |> Keyword.fetch!(:app_id)

    RegentIdentity.HTTP.put_owner(conn, %RegentIdentity.Owner{
      app_id: app_id,
      privy_user_id: privy_user_id
    })
  end

  defp refuse(conn, code) do
    {status, message, hint} = Map.fetch!(AgentWallet.not_person_refusals(), code)
    conn |> ExactResponse.send_error(status, code, message, hint) |> halt()
  end
end
