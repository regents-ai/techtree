defmodule TechtreeWeb.PairingBox do
  @moduledoc """
  Pairing an agent (`RegentAgents`), under "Pair New Agent" in the side panel on
  every page, in the shared pairing box (`Regent.Account.pairing`): the message to
  paste with its code in a short box with icons to copy it and make a new code,
  then the ten agents in `RegentAgents.Harness.featured/0` to choose from by
  their pictures. Once the agent uses the code, the box names it.

  The parent passes `account` (the signed-in account), its `session_lease` as
  `lease` and `id`, and sends `agents_changed: true` when an agent pairs, checks
  in or is unpaired anywhere.
  """
  use TechtreeWeb, :live_component

  alias RegentAgents.{Harness, PairingCode, PairingMessage, Person}
  alias TechtreeWeb.Live.Session

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
         true <- harness in Harness.featured() do
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
        harnesses={choices()}
        layout={:icons}
        phx-change="issue_pairing_code"
        phx-submit="issue_pairing_code"
        phx-target={@myself}
        {pairing(@pairing)}
      />
    </div>
    """
  end

  @doc "The ten agents to choose from, as the shared pairing box takes them."
  def choices,
    do:
      for(
        harness <- Harness.featured(),
        do: %{value: to_string(harness), label: label(harness)}
      )

  defp label(:other), do: "Any agent"
  defp label(:codex), do: "OpenAI Codex"
  defp label(harness), do: Harness.label(harness)

  # The pairing box's state; the box keeps one size whatever it holds.
  defp pairing(%{harness: harness, code: %PairingCode.Issued{} = code}) do
    %{
      chosen: to_string(harness),
      message: agent_message(code.code, harness),
      expires_iso: DateTime.to_iso8601(code.expires_at),
      expires: Calendar.strftime(code.expires_at, "%H:%M UTC")
    }
  end

  defp pairing(%{harness: harness, code: {:paired, agent}}),
    do: %{chosen: to_string(harness), outcome: {:paired, agent.name}}

  defp pairing(%{harness: harness, code: :unavailable}),
    do: %{chosen: to_string(harness), outcome: :unavailable}

  defp pairing(nil), do: %{}

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
