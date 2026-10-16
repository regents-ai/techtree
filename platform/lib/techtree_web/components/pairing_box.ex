defmodule TechtreeWeb.PairingBox do
  @moduledoc """
  Pairing an agent (`RegentAgents`): choosing it, the message to paste it with
  its code, "Make a new code", and the agent's name once it uses the code, in the
  shared pairing box (`Regent.Account.pairing`). The Account page's agents and
  the right side panel each hold one.

  The parent passes `account` (the signed-in account), its `session_lease` as
  `lease` and `id`, and sends `agents_changed: true` when an agent pairs, checks
  in or is unpaired anywhere.
  """
  use TechtreeWeb, :live_component

  alias RegentAgents.{Harness, PairingCode, PairingMessage, Person}
  alias TechtreeWeb.Live.Session

  # Stands in for a code before one is made, so the message keeps its size.
  @no_code String.duplicate("X", 24)

  @impl true
  def mount(socket),
    do:
      {:ok,
       socket
       |> Session.check_component_lease(&take_account/2)
       |> assign(pairing: nil)}

  @impl true
  def update(%{agents_changed: true}, socket), do: {:ok, after_pairing(socket)}

  def update(%{account: account, id: id, lease: lease}, socket),
    do: {:ok, socket |> assign(id: id, lease: lease) |> take_account(account)}

  # The account as the page gave it, or as it reads now before each event
  # (`Session.check_component_lease/2`).
  defp take_account(socket, account),
    do: assign(socket, person: %Person{privy_user_id: account.privy_user_id})

  # Choosing an agent, or asking again for the chosen one, makes a code with that
  # agent's message; codes made before keep working until they expire.
  @impl true
  def handle_event("issue_pairing_code", %{"harness" => harness}, socket) do
    with {:ok, harness} <- Harness.match(harness),
         true <- harness in Harness.offered() do
      {:noreply, issue(socket, harness)}
    else
      _not_offered -> {:noreply, socket}
    end
  end

  @impl true
  def render(assigns) do
    ~H"""
    <div>
      <Regent.Account.pairing
        id={@id}
        harnesses={harnesses()}
        phx-change="issue_pairing_code"
        phx-submit="issue_pairing_code"
        phx-target={@myself}
        {pairing(@pairing)}
      />
    </div>
    """
  end

  defp harnesses,
    do:
      for(
        harness <- Harness.offered(),
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
    do: Harness.offered() |> Enum.map(&agent_message(code, &1)) |> Enum.uniq()

  # A code on screen gives way to the agent that used it, so a spent code is
  # never left there to send again.
  defp after_pairing(
         %{assigns: %{pairing: %{code: %PairingCode.Issued{issued_at: issued_at}} = shown}} =
           socket
       ) do
    with {:ok, agents} <- RegentAgents.list_my_agents(actor: socket.assigns.person),
         %{} = agent <- Enum.find(agents, &(DateTime.compare(&1.paired_at, issued_at) != :lt)) do
      assign(socket, pairing: %{shown | code: {:paired, agent}})
    else
      _unchanged -> socket
    end
  end

  defp after_pairing(socket), do: socket

  defp issue(socket, harness) do
    code =
      case RegentAgents.issue_pairing_code(actor: socket.assigns.person) do
        {:ok, issued} -> issued
        {:error, _error} -> :unavailable
      end

    assign(socket, pairing: %{harness: harness, code: code})
  end

  # What the person pastes to their agent.
  defp agent_message(code, harness),
    do: PairingMessage.text(code, "Techtree", TechtreeWeb.Endpoint.url(), harness)
end
