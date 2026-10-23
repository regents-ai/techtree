defmodule TechtreeWeb.AgentsPanel do
  @moduledoc """
  The agents a person has paired with their account (`RegentAgents`), on the
  Account page, in the shared agents list (`Regent.Account.agents`), with Pair
  New Agent opening the side panel's pairing box (`TechtreeWeb.PairingBox`),
  and a larger view of one agent with where it has been active across the Regent
  sites, a line for each site and day (`Techtree.Agents.ActivityReading`), its
  name, which the person may change, and Unpair.

  Pairing immediately lets an agent do what `TechtreeWeb.Capabilities.may/0`
  lists, which the list's tip and the agent's view show the person, and the
  agent's view adds what it has spent of their Credits. World ID is optional. It never touches their wallet (`TechtreeWeb.Plugs.AgentWallet`).
  Pairing is shared by every Regent site, so an agent paired on another one is
  listed here too.

  The parent passes `account` (the signed-in account), its `session_lease` as
  `lease` and `id`, and sends `agents_changed: true` when an agent pairs, checks
  in or is unpaired anywhere.
  """
  use TechtreeWeb, :live_component

  alias Regent.Primitives, as: P
  alias RegentAgents.{Harness, HumanBacking, PairedAgent, Person}
  alias Techtree.Agents.ActivityReading
  alias Techtree.Credits
  alias TechtreeWeb.Capabilities
  alias TechtreeWeb.Live.Session

  @name_refused "That name can’t be used. Use 1 to 80 characters with no hidden characters."

  @impl true
  def mount(socket),
    do:
      {:ok,
       socket
       |> Session.check_component_lease(&take_account/2)
       |> assign(detail: nil, notice: nil, name_error: nil)}

  @impl true
  def update(%{agents_changed: true}, socket), do: {:ok, read_agents(socket)}

  def update(%{account: account, id: id, lease: lease}, socket) do
    {:ok,
     socket
     |> assign(id: id, lease: lease)
     |> take_account(account)
     |> read_agents()}
  end

  # The account as the page gave it, or as it reads now before each event and
  # each background result (`Session.check_component_lease/2`).
  defp take_account(socket, account),
    do:
      assign(socket,
        account: account,
        person: %Person{privy_user_id: account.privy_user_id},
        credits: Credits.person(account)
      )

  @impl true
  def handle_event("open_agent", %{"id" => id}, socket),
    do: {:noreply, socket |> assign(notice: nil, name_error: nil) |> show_agent(id)}

  def handle_event("close_agent", _params, socket),
    do: {:noreply, assign(socket, detail: nil, notice: nil, name_error: nil)}

  # A name the shared rule refuses (blank, over 80 characters or holding a hidden
  # character) is said beside the field; the agent keeps its name.
  def handle_event("rename_agent", %{"agent_id" => id, "name" => name}, socket) do
    actor = socket.assigns.person

    renamed =
      with {:ok, id} <- Ecto.UUID.cast(id),
           {:ok, %PairedAgent{} = agent} <- RegentAgents.get_my_agent(id, actor: actor) do
        RegentAgents.rename_agent(agent, name, actor: actor)
      end

    {notice, name_error} =
      case renamed do
        {:ok, %PairedAgent{name: name}} ->
          {{:status, "Saved. This agent is now called #{name} on every Regent site."}, nil}

        {:ok, nil} ->
          {{:alert, "This agent is no longer paired with your account. Nothing changed."}, nil}

        {:error, %Ash.Error.Invalid{errors: errors}} ->
          if Enum.any?(errors, &match?(%{field: :name}, &1)),
            do: {nil, @name_refused},
            else: {failed_notice(), nil}

        _failed ->
          {failed_notice(), nil}
      end

    {:noreply, socket |> read_agents() |> assign(notice: notice, name_error: name_error)}
  end

  def handle_event("unpair_agent", %{"id" => id}, socket) do
    actor = socket.assigns.person

    notice =
      with {:ok, id} <- Ecto.UUID.cast(id),
           {:ok, %PairedAgent{} = agent} <- RegentAgents.get_my_agent(id, actor: actor),
           :ok <- RegentAgents.unpair_agent(agent, actor: actor) do
        {:status, "#{agent.name} is unpaired. It will need a new code to pair again."}
      else
        {:ok, nil} ->
          {:alert, "This agent is no longer paired with your account. Nothing changed."}

        _failed ->
          failed_notice()
      end

    {:noreply, socket |> read_agents() |> assign(notice: notice)}
  end

  defp failed_notice,
    do: {:alert, "Your agents couldn’t be updated just now. Nothing changed. Try again."}

  # Where the open agent has been active and its registry listing, landing only
  # while that agent is still open.
  @impl true
  def handle_async({:agent_activity, id}, result, socket) do
    case socket.assigns.detail do
      %{agent: %{id: ^id}} = detail ->
        {:noreply, assign(socket, detail: activity_read(detail, result))}

      _moved_on ->
        {:noreply, socket}
    end
  end

  # What the open agent has spent, landing only while that agent is still open.
  def handle_async({:agent_spent, id}, result, socket) do
    case socket.assigns.detail do
      %{agent: %{id: ^id}} = detail ->
        {:noreply, assign(socket, detail: %{detail | spent: spent(result)})}

      _moved_on ->
        {:noreply, socket}
    end
  end

  defp spent({:ok, {:ok, amount}}), do: RegentCredits.Amount.format(amount)
  defp spent(_failed), do: :unavailable

  defp activity_read(detail, {:ok, {:ok, reading}}),
    do: %{detail | activity: reading.days, listing: reading.listing}

  defp activity_read(detail, _failed), do: %{detail | activity: :unavailable}

  @impl true
  def render(assigns) do
    ~H"""
    <div class="account-agents">
      <Regent.Account.agents
        id={@id}
        agents={rows(@agents, @now)}
        notice={if is_nil(@detail), do: notice_text(@notice)}
      >
        <:about>Once paired, an agent may: {may_words()}.</:about>
        <:actions :let={agent}>
          <P.button
            type="button"
            variant="quiet"
            phx-click="open_agent"
            phx-value-id={agent.id}
            phx-target={@myself}
            aria-label={"See what #{agent.name} has done"}
          >
            See what it has done
          </P.button>
          <P.button
            type="button"
            variant="quiet"
            phx-click="unpair_agent"
            phx-value-id={agent.id}
            phx-target={@myself}
            aria-label={"Unpair #{agent.name}"}
            data-confirm={"Unpair #{agent.name}? It will need a new code to pair again."}
          >
            Unpair
          </P.button>
        </:actions>
        <:footer>
          <P.button type="button" variant="secondary" data-aside-open>Pair New Agent</P.button>

          <Regent.Account.agent_detail
            :if={@detail}
            id="account-agent-dialog"
            agent={detail_agent(@detail, @now)}
            verified={HumanBacking.describe(@detail.agent).human_backed}
            same_person_count={HumanBacking.describe(@detail.agent).same_person_agent_count}
            same_person={same_person(@agents, @detail.agent)}
            may={Capabilities.may()}
            spent={@detail.spent}
            activity={activity(@detail.activity)}
            notice={@notice}
            target={@myself}
            open_event="open_agent"
            rename_event="rename_agent"
            name_error={@name_error}
            phx-hook="InfoDialog"
            data-open
            data-close-event="close_agent"
          >
            <:actions>
              <P.button
                type="button"
                variant="secondary"
                phx-click="unpair_agent"
                phx-value-id={@detail.agent.id}
                phx-target={@myself}
                data-confirm={"Unpair #{@detail.agent.name}? It will need a new code to pair again."}
              >
                Unpair
              </P.button>
            </:actions>
          </Regent.Account.agent_detail>
        </:footer>
      </Regent.Account.agents>
    </div>
    """
  end

  @doc "Each agent as the shared list shows it, newest first as the account reads them."
  def rows(:unavailable, _now), do: :unavailable

  def rows(agents, now) do
    Enum.map(agents, fn agent ->
      %{
        id: agent.id,
        name: agent.name,
        kind: to_string(agent.harness),
        harness: Harness.label(agent.harness),
        wallet: agent.wallet,
        backed: HumanBacking.describe(agent).human_backed,
        last_contact_iso: DateTime.to_iso8601(agent.last_contact_at),
        last_contact: RegentFormat.relative_time(agent.last_contact_at, now),
        light: nil,
        light_label: nil
      }
    end)
  end

  # The tip's one sentence: each line, lower-cased, apart by semicolons since
  # some lines hold commas of their own.
  defp may_words,
    do:
      Enum.map_join(
        Capabilities.may(),
        "; ",
        &(String.downcase(String.first(&1)) <> String.slice(&1, 1..-1//1))
      )

  defp notice_text({_role, text}), do: text
  defp notice_text(nil), do: nil

  # The person's other agents paired with this account, grouped by the World ID
  # person saved behind each.
  defp same_person(agents, %{id: id, human_id: human_id})
       when is_list(agents) and is_binary(human_id),
       do: Enum.filter(agents, &(&1.human_id == human_id and &1.id != id))

  defp same_person(_agents, _agent), do: []

  defp detail_agent(%{agent: agent, listing: listing}, now) do
    %{
      id: agent.id,
      name: agent.name,
      kind: to_string(agent.harness),
      harness: Harness.label(agent.harness),
      wallet: agent.wallet,
      wallet_label: RegentFormat.short_address(agent.wallet),
      listing: listing,
      paired_at: moment(agent.paired_at),
      last_contact: RegentFormat.relative_time(agent.last_contact_at, now),
      last_contact_at: moment(agent.last_contact_at)
    }
  end

  defp activity(days) when is_list(days) do
    Enum.map(days, fn line ->
      %{
        site: line.site,
        day_iso: Date.to_iso8601(line.day),
        day: Calendar.strftime(line.day, "%-d %B %Y"),
        hours: hours(line.first_seen_at, line.last_seen_at)
      }
    end)
  end

  defp activity(state), do: state

  # The open agent is read again with the list, so its dialog closes on its own
  # once the agent is unpaired.
  defp read_agents(socket) do
    agents =
      case RegentAgents.list_my_agents(actor: socket.assigns.person) do
        {:ok, agents} -> agents
        {:error, _error} -> :unavailable
      end

    socket = assign(socket, agents: agents, now: DateTime.utc_now())

    case socket.assigns.detail do
      %{agent: %{id: id}} -> show_agent(socket, id)
      nil -> socket
    end
  end

  # Where the agent has been active and its registry listing come from its
  # shared reading in the background, and what it has spent from the person's
  # Credits. What is already on screen for this agent stays until the new
  # reading lands.
  defp show_agent(socket, id) do
    with {:ok, id} <- Ecto.UUID.cast(id),
         {:ok, %PairedAgent{} = agent} <-
           RegentAgents.get_my_agent(id, actor: socket.assigns.person) do
      case socket.assigns.detail do
        %{agent: %{id: ^id}} = shown ->
          socket |> assign(detail: %{shown | agent: agent}) |> read_detail(agent)

        _other ->
          socket
          |> assign(detail: %{agent: agent, activity: :loading, listing: nil, spent: :loading})
          |> read_detail(agent)
      end
    else
      _missing -> assign(socket, detail: nil)
    end
  end

  defp read_detail(socket, agent) do
    credits = socket.assigns.credits

    socket
    |> start_async({:agent_activity, agent.id}, fn -> ActivityReading.read(agent) end)
    |> start_async({:agent_spent, agent.id}, fn -> Credits.spent_by(credits, agent.wallet) end)
  end

  # When the day's first and last request came, or the one time when they share
  # a minute.
  defp hours(first, last) do
    {from, to} = {Calendar.strftime(first, "%H:%M"), Calendar.strftime(last, "%H:%M")}
    if from == to, do: "#{to} UTC", else: "#{from} to #{to} UTC"
  end

  defp moment(datetime), do: Calendar.strftime(datetime, "%-d %B %Y, %H:%M UTC")
end
