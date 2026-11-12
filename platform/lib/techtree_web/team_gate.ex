defmodule TechtreeWeb.TeamGate do
  @moduledoc """
  Keeps the team's own pages (`/admin/messages`) for the site's admins: a
  signed-in account whose Privy id the `:admins` setting of `:regent_agents`
  names (config/runtime.exs), the same list `RegentAgents.Checks.Admin` reads
  in each policy. Anyone else gets the site's ordinary not-found page, so the
  page's existence is not shown either.

  As a plug it checks the request. As an `on_mount` hook it checks the person
  the session loaded (`TechtreeWeb.Live.Session`, `:load_human`, which comes
  before it and re-reads the sign-in on every navigation and press). A page
  takes its actor from `admin/1` each time it reads, so a sign-in that ends or
  lapses cannot keep reading.
  """

  @behaviour Plug

  alias Techtree.Accounts.SessionAuthority

  @impl Plug
  def init(opts), do: opts

  @impl Plug
  def call(conn, _opts) do
    {_lineage, account, _lapses_at} =
      conn |> Plug.Conn.get_session() |> SessionAuthority.claim() |> SessionAuthority.resolve()

    if admin(account),
      do: conn,
      else: raise(Phoenix.Router.NoRouteError, conn: conn, router: TechtreeWeb.Router)
  end

  def on_mount(:default, _params, _session, socket) do
    if admin(socket.assigns.access_context),
      do: {:cont, socket},
      else: {:halt, Phoenix.LiveView.redirect(socket, to: "/")}
  end

  @doc """
  The team actor for the signed-in person of an access context or an account,
  or `nil` when no one is signed in or the person is not one of the admins.
  """
  @spec admin(map() | nil) :: RegentAgents.Person.t() | nil
  def admin(%{principal: {:human, account}}), do: admin(account)

  def admin(%{privy_user_id: id}) when is_binary(id) do
    if id in Application.get_env(:regent_agents, :admins, []),
      do: %RegentAgents.Person{privy_user_id: id, role: :admin}
  end

  def admin(_signed_out), do: nil
end
