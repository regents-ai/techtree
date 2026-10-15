defmodule TechtreeWeb.AgentsPanel do
  @moduledoc """
  The agents a person has paired with their account (`RegentAgents`), in the
  shared agents list (`Regent.Account.agents`), a way to pair another by
  choosing it and pasting it a message, and a larger view of one agent with
  what it has done across the Regent sites (`RegentAgents.Activity`) and
  Unpair.

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

  alias RegentAgents.{
    Activity,
    Harness,
    HumanBacking,
    PairedAgent,
    PairingCode,
    PairingMessage,
    Person
  }

  alias Techtree.Credits
  alias TechtreeWeb.Capabilities
  alias TechtreeWeb.Live.Session

  # Stands in for a code before one is made, so the message keeps its size.
  @no_code String.duplicate("X", 24)

  @impl true
  def mount(socket),
    do:
      {:ok,
       socket
       |> Session.check_component_lease(&take_account/2)
       |> assign(pairing: nil, detail: nil, notice: nil)}

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
        person: %Person{privy_user_id: account.privy_user_id},
        credits: Credits.person(account)
      )

  # Choosing an agent, or asking again for the chosen one, makes a code with that
  # agent's message; codes made before keep working until they expire.
  @impl true
  def handle_event("issue_pairing_code", %{"harness" => harness}, socket) do
    case Harness.match(harness) do
      {:ok, harness} -> {:noreply, issue(socket, harness)}
      :error -> {:noreply, socket}
    end
  end

  def handle_event("open_agent", %{"id" => id}, socket),
    do: {:noreply, socket |> assign(notice: nil) |> show_agent(id)}

  def handle_event("close_agent", _params, socket),
    do: {:noreply, assign(socket, detail: nil, notice: nil)}

  def handle_event("load_more_activity", %{"id" => id}, socket),
    do: {:noreply, load_more_activity(socket, id)}

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
          {:alert, "Your agents couldn’t be updated just now. Nothing changed. Try again."}
      end

    {:noreply, socket |> read_agents() |> assign(notice: notice)}
  end

  # The newest page of what the open agent has done and its registry listing,
  # landing only while that agent is still open and its older activity has not
  # been asked for.
  @impl true
  def handle_async({:agent_activity, id}, result, socket) do
    case socket.assigns.detail do
      %{agent: %{id: ^id}, paged: false} = detail ->
        {:noreply, assign(socket, detail: first_page(detail, result))}

      _moved_on ->
        {:noreply, socket}
    end
  end

  # The next page of the open agent's activity, added below what is shown.
  def handle_async({:more_agent_activity, id}, result, socket) do
    case socket.assigns.detail do
      %{agent: %{id: ^id}, more: :loading} = detail ->
        {:noreply, assign(socket, detail: next_page(detail, result))}

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

  defp first_page(detail, {:ok, {:ok, page}}),
    do: %{detail | activity: page.entries, next: page.next, listing: page.listing}

  defp first_page(detail, _failed), do: %{detail | activity: :unavailable}

  defp next_page(detail, {:ok, {:ok, page}}),
    do: %{detail | activity: detail.activity ++ page.entries, next: page.next, more: :idle}

  defp next_page(detail, _failed), do: %{detail | more: :unavailable}

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
          <Regent.Account.pairing
            id={"#{@id}-pair"}
            harnesses={harnesses()}
            phx-change="issue_pairing_code"
            phx-submit="issue_pairing_code"
            phx-target={@myself}
            {pairing(@pairing)}
          />

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
            more={if is_list(@detail.activity) and is_binary(@detail.next), do: @detail.more}
            notice={@notice}
            target={@myself}
            open_event="open_agent"
            more_event="load_more_activity"
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

  # Each agent as the shared list shows it, newest first as the account reads them.
  defp rows(:unavailable, _now), do: :unavailable

  defp rows(agents, now) do
    Enum.map(agents, fn agent ->
      %{
        id: agent.id,
        name: agent.name,
        kind: to_string(agent.harness),
        harness: Harness.label(agent.harness),
        backed: HumanBacking.describe(agent).human_backed,
        last_contact_iso: DateTime.to_iso8601(agent.last_contact_at),
        last_contact: RegentFormat.relative_time(agent.last_contact_at, now)
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

  defp harnesses,
    do:
      for(
        harness <- Harness.values(),
        do: %{value: to_string(harness), label: Harness.label(harness)}
      )

  # The pairing box's state. Every agent's message is drawn, the chosen one shown,
  # so the box keeps one size; before a code is made a stand-in holds its place.
  defp pairing(%{harness: harness, code: %PairingCode.Issued{} = code}) do
    %{
      chosen: to_string(harness),
      messages: messages(code.code),
      message: agent_message(code.code, harness),
      expires_iso: DateTime.to_iso8601(code.expires_at),
      expires: Calendar.strftime(code.expires_at, "%H:%M UTC")
    }
  end

  defp pairing(%{harness: harness, code: {:paired, agent}}),
    do: %{
      chosen: to_string(harness),
      messages: messages(@no_code),
      outcome: {:paired, agent.name}
    }

  defp pairing(%{harness: harness, code: :unavailable}),
    do: %{chosen: to_string(harness), messages: messages(@no_code), outcome: :unavailable}

  defp pairing(nil), do: %{messages: messages(@no_code)}

  defp messages(code),
    do: Harness.values() |> Enum.map(&agent_message(code, &1)) |> Enum.uniq()

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
      listing: listing,
      paired_at: moment(agent.paired_at),
      last_contact: RegentFormat.relative_time(agent.last_contact_at, now),
      last_contact_at: moment(agent.last_contact_at)
    }
  end

  defp activity(entries) when is_list(entries) do
    Enum.map(entries, fn entry ->
      %{
        action: entry.action,
        site: entry.site,
        occurred_at_iso: DateTime.to_iso8601(entry.occurred_at),
        occurred_at: moment(entry.occurred_at)
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

    socket =
      assign(socket,
        agents: agents,
        now: DateTime.utc_now(),
        pairing: after_pairing(socket.assigns.pairing, agents)
      )

    case socket.assigns.detail do
      %{agent: %{id: id}} -> show_agent(socket, id)
      nil -> socket
    end
  end

  # A code on screen gives way to the agent that used it, so a spent code is
  # never left there to send again.
  defp after_pairing(%{code: %PairingCode.Issued{issued_at: issued_at}} = shown, agents)
       when is_list(agents) do
    case Enum.find(agents, &(DateTime.compare(&1.paired_at, issued_at) != :lt)) do
      nil -> shown
      agent -> %{shown | code: {:paired, agent}}
    end
  end

  defp after_pairing(shown, _agents), do: shown

  defp issue(socket, harness) do
    code =
      case RegentAgents.issue_pairing_code(actor: socket.assigns.person) do
        {:ok, issued} -> issued
        {:error, _error} -> :unavailable
      end

    assign(socket, pairing: %{harness: harness, code: code}, notice: nil)
  end

  # What the agent has done and its registry listing are read from the sign-in
  # service in the background, and what it has spent from the person's Credits.
  # What is already on screen for this agent stays until the new reading lands.
  # Once the person has asked for older activity, the list stays as they are
  # reading it.
  defp show_agent(socket, id) do
    with {:ok, id} <- Ecto.UUID.cast(id),
         {:ok, %PairedAgent{} = agent} <-
           RegentAgents.get_my_agent(id, actor: socket.assigns.person) do
      case socket.assigns.detail do
        %{agent: %{id: ^id}, paged: true} = shown ->
          assign(socket, detail: %{shown | agent: agent})

        %{agent: %{id: ^id}} = shown ->
          socket |> assign(detail: %{shown | agent: agent}) |> read_detail(agent)

        _other ->
          socket
          |> assign(
            detail: %{
              agent: agent,
              activity: :loading,
              next: nil,
              more: :idle,
              paged: false,
              listing: nil,
              spent: :loading
            }
          )
          |> read_detail(agent)
      end
    else
      _missing -> assign(socket, detail: nil)
    end
  end

  defp read_detail(socket, agent) do
    credits = socket.assigns.credits

    socket
    |> start_async({:agent_activity, agent.id}, fn ->
      Activity.recent(agent, Capabilities.requests())
    end)
    |> start_async({:agent_spent, agent.id}, fn -> Credits.spent_by(credits, agent.wallet) end)
  end

  defp load_more_activity(
         %{assigns: %{detail: %{agent: %{id: id} = agent, next: next, more: more} = detail}} =
           socket,
         id
       )
       when is_binary(next) and more != :loading do
    socket
    |> assign(detail: %{detail | more: :loading, paged: true})
    |> start_async({:more_agent_activity, id}, fn ->
      Activity.recent(agent, Capabilities.requests(), next)
    end)
  end

  defp load_more_activity(socket, _id), do: socket

  # What the person pastes to their agent.
  defp agent_message(code, harness),
    do: PairingMessage.text(code, "Ash Template", TechtreeWeb.Endpoint.url(), harness)

  defp moment(datetime), do: Calendar.strftime(datetime, "%-d %B %Y, %H:%M UTC")
end
