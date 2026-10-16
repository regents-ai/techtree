defmodule TechtreeWeb.PanelAgents do
  @moduledoc """
  The agents paired with the person's account (`RegentAgents`), first in the side
  panel on every page, in the shared short list (`Regent.Account.agents_brief`):
  each agent's picture and name over the Regent site it was last active on and
  how long ago. Pairing is shared by every Regent site, so an agent paired on
  another one is listed too. The Account page's list
  (`TechtreeWeb.AgentsPanel`) opens one and unpairs it.

  Where each agent was last active comes from its shared reading
  (`Techtree.Agents.ActivityReading`), asked for only for an open panel: the
  `PanelAgents` hook asks when the page arrives with the panel open and each time
  it opens, and a request while one is still out is let go. A pairing, check-in
  or unpairing updates the list at once; the lines follow on the next opening.

  The parent passes `account` (the signed-in account), its `session_lease` as
  `lease` and `id`, and sends `agents_changed: true` when an agent pairs, checks
  in or is unpaired anywhere.
  """
  use TechtreeWeb, :live_component

  alias RegentAgents.{Activity, Person}
  alias Techtree.Agents.ActivityReading
  alias TechtreeWeb.Live.Session

  @impl true
  def mount(socket),
    do:
      {:ok,
       socket
       |> Session.check_component_lease(&take_account/2)
       |> assign(last_actions: %{}, reading: false)}

  @impl true
  def update(%{agents_changed: true}, socket), do: {:ok, read_agents(socket)}

  def update(%{account: account, id: id, lease: lease}, socket),
    do: {:ok, socket |> assign(id: id, lease: lease) |> take_account(account) |> read_agents()}

  # The account as the page gave it, or as it reads now before each event
  # (`Session.check_component_lease/2`).
  defp take_account(socket, account),
    do: assign(socket, person: %Person{privy_user_id: account.privy_user_id})

  @impl true
  def handle_event("read_last_actions", _params, socket),
    do: {:noreply, read_last_actions(socket)}

  @impl true
  def handle_async(:last_actions, {:ok, last_actions}, socket),
    do:
      {:noreply,
       assign(socket, last_actions: last_actions, reading: false, now: DateTime.utc_now())}

  def handle_async(:last_actions, {:exit, _reason}, socket),
    do: {:noreply, assign(socket, reading: false)}

  @impl true
  def render(assigns) do
    ~H"""
    <div id={"#{@id}-reader"} phx-hook="PanelAgents" data-read-on-open>
      <Regent.Account.agents_brief id={@id} agents={rows(@agents, @last_actions, @now)} />
    </div>
    """
  end

  defp read_agents(socket) do
    agents =
      case RegentAgents.list_my_agents(actor: socket.assigns.person) do
        {:ok, agents} -> agents
        {:error, _error} -> :unavailable
      end

    assign(socket, agents: agents, now: DateTime.utc_now())
  end

  defp read_last_actions(%{assigns: %{reading: false, agents: agents}} = socket)
       when is_list(agents),
       do:
         socket
         |> assign(reading: true)
         |> start_async(:last_actions, fn -> last_actions(agents) end)

  defp read_last_actions(socket), do: socket

  # Where and when each agent was last active, by id; an agent whose reading
  # fails or crashes, or that has not been active since it paired, is left out,
  # and its line stays empty. The reads are not linked to the page, so one that
  # crashes ends only itself.
  defp last_actions(agents) do
    Techtree.Agents.Reads
    |> Task.Supervisor.async_stream_nolink(agents, &{&1.id, last_action(&1)},
      max_concurrency: 4,
      timeout: 8_000,
      on_timeout: :kill_task
    )
    |> Enum.flat_map(fn
      {:ok, {id, %{} = latest}} -> [{id, latest}]
      _unread -> []
    end)
    |> Map.new()
  end

  defp last_action(agent) do
    case ActivityReading.read(agent) do
      {:ok, reading} -> Activity.latest(reading)
      {:error, _reason} -> nil
    end
  end

  defp rows(:unavailable, _last_actions, _now), do: :unavailable

  defp rows(agents, last_actions, now) do
    Enum.map(agents, fn agent ->
      latest = last_actions[agent.id]

      %{
        id: agent.id,
        name: agent.name,
        kind: to_string(agent.harness),
        last_action: latest && "Active on #{latest.site}",
        last_action_iso: latest && DateTime.to_iso8601(latest.at),
        last_action_at: latest && RegentFormat.short_relative_time(latest.at, now)
      }
    end)
  end
end
