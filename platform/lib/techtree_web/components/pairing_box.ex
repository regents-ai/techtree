defmodule TechtreeWeb.PairingBox do
  @moduledoc """
  Pairing an agent (`RegentAgents`), in the pairing window every Pair New Agent
  opens, in the shared pairing box (`Regent.Account.pairing`): a dropdown of the
  ten agents in `RegentAgents.Harness.featured/0`, and Claude while its connector
  is on (`RegentAgents.Harness.hosted/0`, read at runtime), then the message to paste with
  its code in a short box with icons to copy it and make a new code. Each agent
  keeps its own code until it expires, so choosing another agent and coming back
  shows the same message. Once the agent uses the code, the box names it, and this
  site's own line for it, if it has one, is under the box (`TechtreeWeb.AccountSite`).

  The parent passes `account` (the signed-in account), its `session_lease` as
  `lease` and `id`, and sends `agents_changed: true` when an agent pairs, checks
  in or is unpaired anywhere.
  """
  use TechtreeWeb, :live_component

  alias RegentAgents.{Harness, PairingCode, PairingMessage, Person}
  alias TechtreeWeb.AccountSite
  alias TechtreeWeb.Live.Session
  alias TechtreeWeb.VisitLog

  require Logger

  @impl true
  def mount(socket),
    do:
      {:ok,
       socket
       |> Session.check_component_lease(&take_account/2)
       |> assign(chosen: nil, codes: %{})}

  @impl true
  def update(%{agents_changed: true}, socket), do: {:ok, after_pairing(socket)}

  def update(%{account: account, id: id, lease: lease}, socket),
    do: {:ok, socket |> assign(id: id, lease: lease) |> take_account(account)}

  # The account as the page gave it, or as it reads now before each event
  # (`Session.check_component_lease/2`).
  defp take_account(socket, account),
    do: assign(socket, account: account, person: %Person{privy_user_id: account.privy_user_id})

  # Choosing an agent shows its code, made the first time it is chosen and again
  # once it has expired; asking for a new code replaces the chosen agent's. Codes
  # made before keep working until they expire.
  @impl true
  def handle_event("choose_agent", %{"harness" => harness}, socket),
    do: {:noreply, with_offered(socket, harness, &show/2)}

  def handle_event("new_pairing_code", %{"harness" => harness}, socket),
    do: {:noreply, with_offered(socket, harness, &issue/2)}

  # Nothing chosen: a reconnecting page restores the form with no agent picked,
  # and a submit can come before a choice. The box stays as it is.
  def handle_event(event, _nothing_chosen, socket)
      when event in ["choose_agent", "new_pairing_code"],
      do: {:noreply, socket}

  @impl true
  def render(assigns) do
    ~H"""
    <div>
      <Regent.Account.pairing
        id={@id}
        harnesses={choices()}
        phx-change="choose_agent"
        phx-submit="new_pairing_code"
        phx-target={@myself}
        {pairing(@chosen, @codes[@chosen])}
      />
      <AccountSite.paired
        :if={match?({:paired, _agent, _part}, @codes[@chosen])}
        id={"#{@id}-site"}
        agent={elem(@codes[@chosen], 1)}
        part={elem(@codes[@chosen], 2)}
      />
    </div>
    """
  end

  @doc """
  The agents to choose from, as the shared pairing box takes them: the ten
  featured agents, then Claude while its connector is on.
  """
  def choices,
    do:
      for(
        harness <- Harness.featured() ++ Harness.hosted(),
        do: %{value: to_string(harness), label: label(harness)}
      )

  defp label(:other), do: "Any agent"
  defp label(:codex), do: "OpenAI Codex"
  defp label(harness), do: Harness.label(harness)

  # The pairing box's state; the box keeps one size whatever it holds.
  defp pairing(nil, nil), do: %{}

  defp pairing(harness, %PairingCode.Issued{} = code),
    do: %{
      chosen: to_string(harness),
      message: agent_message(code.code, harness),
      expires_iso: DateTime.to_iso8601(code.expires_at),
      expires: Calendar.strftime(code.expires_at, "%H:%M UTC")
    }

  defp pairing(harness, {:paired, agent, _part}),
    do: %{chosen: to_string(harness), outcome: {:paired, agent.name}}

  defp pairing(harness, :unavailable), do: %{chosen: to_string(harness), outcome: :unavailable}

  defp with_offered(socket, harness, then) do
    with {:ok, harness} <- Harness.match(harness),
         true <- harness in Harness.offered() do
      then.(socket, harness)
    else
      _not_offered -> socket
    end
  end

  defp show(socket, harness) do
    socket = assign(socket, chosen: harness)
    if usable?(socket.assigns.codes[harness]), do: socket, else: issue(socket, harness)
  end

  # A code still in time, or the agent that used it; a missing, expired or failed
  # code is made again.
  defp usable?(%PairingCode.Issued{expires_at: expires_at}),
    do: DateTime.after?(expires_at, DateTime.utc_now())

  defp usable?({:paired, _agent, _part}), do: true
  defp usable?(_missing_or_unavailable), do: false

  # Each code on screen gives way to the agent that used it, so a spent code is
  # never left there to send again, and an agent shows under its own code only.
  defp after_pairing(%{assigns: %{codes: codes, person: person}} = socket) do
    held = for {harness, %PairingCode.Issued{code: code}} <- codes, into: %{}, do: {code, harness}

    with true <- held != %{},
         {:ok, paired} <- RegentAgents.agents_paired_with(Map.keys(held), actor: person) do
      parts =
        AccountSite.read(socket.assigns.account, Enum.map(paired, fn {_code, a} -> a.wallet end))

      assign(socket, codes: Enum.reduce(paired, codes, &paired(&1, &2, held, parts)))
    else
      _unchanged -> socket
    end
  end

  defp paired({code, agent}, codes, held, parts) do
    VisitLog.step("agent_paired", to_string(held[code]))
    Map.put(codes, held[code], {:paired, agent, parts[agent.wallet]})
  end

  defp issue(socket, harness) do
    code =
      case RegentAgents.issue_pairing_code(actor: socket.assigns.person) do
        {:ok, issued} ->
          VisitLog.step("pairing_code_shown", to_string(harness))
          issued

        {:error, error} ->
          Logger.warning("A pairing code couldn't be made: #{inspect(failure_kinds(error))}")
          :unavailable
      end

    assign(socket, chosen: harness, codes: Map.put(socket.assigns.codes, harness, code))
  end

  # The kinds of failure alone: the failure's words can hold the person's id.
  defp failure_kinds(%{errors: [_ | _] = errors}), do: Enum.map(errors, & &1.__struct__)
  defp failure_kinds(error), do: [error.__struct__]

  # What the person pastes to their agent.
  defp agent_message(code, harness),
    do: PairingMessage.text(code, TechtreeWeb.Endpoint.url(), harness)
end
