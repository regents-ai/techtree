defmodule TechtreeWeb.AccountShellLive do
  @moduledoc "One template account frame for profile, Credits, Points, wallets and connections."
  use TechtreeWeb, :live_view

  alias Techtree.Accounts
  alias Techtree.Accounts.LinkedIdentity.Providers
  alias Techtree.Actors.Human
  alias TechtreeWeb.{AccountLive, CreditsHistoryLive, Read}
  import TechtreeWeb.Components.AccountControls, only: [credits_control: 1]

  @tabs [
    %{route_id: :account, label: "Account", path: "/account"},
    %{route_id: :points, label: "Points", path: "/account/points"},
    %{route_id: :credits, label: "Credits", path: "/account/credits"},
    %{route_id: :wallets, label: "Wallets", path: "/account/wallets"},
    %{route_id: :connections, label: "Connections", path: "/account/connections"}
  ]
  @actions %{"link" => :link, "unlink" => :unlink}
  @refused %{
    tone: :error,
    message: "That connection couldn’t be updated. Refresh the page and try again."
  }

  @impl true
  def mount(_params, _session, socket) do
    if connected?(socket), do: subscribe_to_own_topics(socket.assigns.access_context)

    {:ok,
     socket
     |> assign(
       tabs: @tabs,
       verified_connections: %Read{},
       points: %Read{},
       credits_read: %Read{},
       credits_history: %Read{},
       points_bonus: %Read{},
       points_earning: [],
       verified_connections_notice: nil,
       connection_outcome: nil
     )
     |> read_credits()}
  end

  @impl true
  def handle_params(_params, _uri, socket) do
    route_spec = Enum.find(@tabs, &(&1.route_id == socket.assigns.live_action))

    {:noreply,
     socket
     |> assign(page_title: route_spec.label, route_spec: route_spec)
     |> load_points(route_spec)
     |> load_credits_history(route_spec)
     |> load_verified_connections(route_spec)}
  end

  @impl true
  def handle_event(
        "request_verified_connection",
        %{"action" => action, "provider" => provider},
        socket
      ) do
    with %Human{} <- human_actor(socket),
         {:ok, provider} <- Providers.parse(provider),
         {:ok, action} <- Map.fetch(@actions, action),
         {:ok, request} <-
           identity_request(action, provider, socket.assigns.verified_connections.value) do
      {:noreply,
       socket
       |> assign(
         verified_connections_notice: %{tone: :info, message: connection_started(request)}
       )
       |> push_event("verified-connections:request", request)}
    else
      _refused -> {:noreply, assign(socket, verified_connections_notice: @refused)}
    end
  end

  # The outcome is judged against the connections read after the provider came
  # back, so it waits for that read to land.
  def handle_event("refresh_verified_connections", params, socket) do
    {:noreply,
     socket
     |> assign(connection_outcome: params, verified_connections_notice: nil)
     |> read_verified_connections()}
  end

  def handle_event("credits_history_older", _params, socket) do
    with %Read{value: %{more?: true} = history} <- socket.assigns.credits_history,
         account when account != nil <- current_account(socket.assigns.access_context) do
      actor = Techtree.Credits.person(account)

      {:noreply,
       Read.start(socket, :credits_history, account.privy_user_id, fn ->
         CreditsHistoryLive.older(history, &RegentCredits.history(&1, actor: actor))
       end)}
    else
      _no_more -> {:noreply, socket}
    end
  end

  @impl true
  def handle_async({Read, :credits_read, _generation} = name, result, socket) do
    {:noreply, Read.settle(socket, name, result)}
  end

  def handle_async({Read, _name, _generation} = name, result, socket) do
    {:noreply, socket |> Read.settle(name, result) |> report_connection_outcome()}
  end

  @impl true
  def handle_info(
        %{topic: "points:" <> _},
        %{assigns: %{route_spec: %{route_id: :points}}} = socket
      ),
      do: {:noreply, read_points(socket)}

  def handle_info(%{topic: "points:" <> _}, socket), do: {:noreply, socket}

  # The balance changed on this or any Regent site: a purchase, a gift, a spend.
  # The header, the Buy Credits panel, the Account page and the Credits history
  # follow.
  def handle_info(:credits_changed, socket) do
    {:noreply, socket |> read_credits() |> load_credits_history(socket.assigns.route_spec)}
  end

  # An agent paired, checked in or was unpaired, here or on another Regent site.
  # The Account tab lists the agents and holds the pairing box; the account menu
  # follows on its own.
  def handle_info(:agents_changed, socket) do
    if socket.assigns.route_spec.route_id == :account do
      send_update(TechtreeWeb.AgentsPanel, id: "account-agents", agents_changed: true)
      send_update(TechtreeWeb.PairingBox, id: "account-pairing-box", agents_changed: true)
    end

    {:noreply, socket}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <div
        id="account-shell"
        class="account-shell"
        phx-hook="AccountShell"
        data-route={@route_spec.path}
      >
        <div class="account-shell__head">
          <nav class="account-shell__tabs" aria-label="Account views">
            <.link
              :for={tab <- @tabs}
              patch={tab.path}
              aria-current={@route_spec.route_id == tab.route_id && "page"}
            >
              {tab.label}
            </.link>
          </nav>
          <div class="account-shell__controls">
            <.credits_control :if={current_account(@access_context)} credits={@credits_read} />
          </div>
        </div>
        <AccountLive.profile
          :if={@route_spec.route_id == :account}
          signed_out_reason={@signed_out_reason}
          lease={@session_lease}
          account={current_account(@access_context)}
          account_control={@account_control}
          credits_read={@credits_read}
        />
        <TechtreeWeb.PointsLive.page
          :if={@route_spec.route_id == :points}
          signed_out_reason={@signed_out_reason}
          account={current_account(@access_context)}
          points={@points}
          bonus={@points_bonus}
          earning={@points_earning}
        />
        <CreditsHistoryLive.page
          :if={@route_spec.route_id == :credits}
          signed_out_reason={@signed_out_reason}
          account={current_account(@access_context)}
          history={@credits_history}
        />
        <AccountLive.wallets
          :if={@route_spec.route_id == :wallets}
          signed_out_reason={@signed_out_reason}
          account={current_account(@access_context)}
        />
        <AccountLive.connections
          :if={@route_spec.route_id == :connections}
          signed_out_reason={@signed_out_reason}
          account={current_account(@access_context)}
          verified_connections={@verified_connections}
          verified_connections_notice={@verified_connections_notice}
        />
        <Regent.Structure.dialog
          :if={current_account(@access_context)}
          id="shell-credits"
          class="shell-credits-dialog"
          aria-label="Buy Credits"
          phx-mounted={JS.ignore_attributes(["open"])}
        >
          <Regent.Primitives.button
            variant="quiet"
            type="button"
            class="shell-credits-dialog__close"
            aria-label="Close"
            data-credits-close
          >
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" /></svg>
          </Regent.Primitives.button>
          <.live_component
            module={TechtreeWeb.CreditsPanel}
            id="credits-panel"
            lease={@session_lease}
            account={current_account(@access_context)}
            credits={@credits_read}
          />
        </Regent.Structure.dialog>
      </div>
    </Layouts.page>
    """
  end

  defp subscribe_to_own_topics(%{principal: {:human, account}}) do
    Phoenix.PubSub.subscribe(Techtree.PubSub, "points:#{account.id}")
    Phoenix.PubSub.subscribe(Techtree.PubSub, RegentCredits.topic(account.privy_user_id))
    Phoenix.PubSub.subscribe(Techtree.PubSub, RegentAgents.topic(account.privy_user_id))
  end

  defp subscribe_to_own_topics(_access_context), do: :ok

  defp current_account(%{principal: {:human, account}}), do: account
  defp current_account(_access_context), do: nil

  defp human_actor(%{assigns: %{access_context: %{principal: {:human, account}}}}),
    do: Human.for_account(account)

  defp human_actor(_socket), do: nil

  defp read_credits(socket) do
    case current_account(socket.assigns.access_context) do
      nil ->
        Read.clear(socket, :credits_read)

      account ->
        Read.start(socket, :credits_read, account.privy_user_id, fn ->
          {:ok, RegentCredits.balance(account.privy_user_id)}
        end)
    end
  end

  # The newest page of the account's Credits history, read again on each change.
  defp load_credits_history(socket, %{route_id: :credits}) do
    case current_account(socket.assigns.access_context) do
      nil ->
        Read.clear(socket, :credits_history)

      account ->
        actor = Techtree.Credits.person(account)

        Read.start(socket, :credits_history, account.privy_user_id, fn ->
          RegentCredits.history(%{}, actor: actor)
        end)
    end
  end

  defp load_credits_history(socket, _route_spec), do: Read.clear(socket, :credits_history)

  # The NFT tier is read from Base once per page open, never on each award notice.
  defp load_points(socket, %{route_id: :points}) do
    socket
    |> assign(:points_earning, RegentPoints.Rules.active())
    |> read_points()
    |> read_points_bonus()
  end

  defp load_points(socket, _), do: socket |> Read.clear(:points) |> Read.clear(:points_bonus)

  defp read_points(socket) do
    case human_actor(socket) do
      %Human{} = actor ->
        Read.start(socket, :points, actor.human_account_id, fn ->
          RegentPoints.summary(actor: actor)
        end)

      nil ->
        Read.clear(socket, :points)
    end
  end

  defp read_points_bonus(socket) do
    case human_actor(socket) do
      %Human{human_account_id: id} ->
        Read.start(socket, :points_bonus, id, fn -> points_bonus(id) end)

      nil ->
        Read.clear(socket, :points_bonus)
    end
  end

  # Base is read for the person's NFTs, counted against the same per-account
  # allowance as the Buy panel's reads.
  defp points_bonus(id) do
    case Techtree.Limits.spend(:wallet_read, {:human, id}) do
      :ok -> RegentPoints.Bonus.current(id)
      :limited -> {:error, :limited}
    end
  end

  defp load_verified_connections(socket, %{route_id: :connections}),
    do: read_verified_connections(socket)

  defp load_verified_connections(socket, _route_spec) do
    socket
    |> Read.clear(:verified_connections)
    |> assign(verified_connections_notice: nil, connection_outcome: nil)
  end

  # The account's own record is the only thing a connection is read from, so
  # nothing the browser reports can name a connection the record does not hold.
  defp read_verified_connections(socket) do
    case human_actor(socket) do
      %Human{} = actor ->
        Read.start(socket, :verified_connections, actor.human_account_id, fn ->
          Accounts.list_my_linked_identities(actor: actor)
        end)

      nil ->
        Read.clear(socket, :verified_connections)
    end
  end

  defp identity_request(:link, provider, _identities),
    do: {:ok, %{action: :link, provider: provider}}

  defp identity_request(:unlink, provider, identities) when is_list(identities) do
    case Enum.find(identities, &(&1.provider == provider)) do
      nil -> :error
      identity -> {:ok, %{action: :unlink, provider: provider, subject: identity.subject}}
    end
  end

  defp identity_request(_action, _provider, _identities), do: :error

  # X and GitHub take the whole tab to their own approval page and bring it
  # back; Farcaster asks for a scan here.
  defp connection_started(%{action: :link, provider: :farcaster}),
    do: "Scan the code with Farcaster to approve the connection."

  defp connection_started(%{action: :link, provider: provider}),
    do: "Taking you to #{Providers.label(provider)} to approve the connection."

  defp connection_started(%{action: :unlink, provider: provider}),
    do: "Disconnecting #{Providers.label(provider)}…"

  defp report_connection_outcome(%{assigns: %{connection_outcome: nil}} = socket), do: socket

  defp report_connection_outcome(
         %{assigns: %{verified_connections: %{state: :loading}}} = socket
       ),
       do: socket

  defp report_connection_outcome(%{assigns: assigns} = socket) do
    notice = connection_outcome(assigns.connection_outcome, assigns.verified_connections)
    assign(socket, verified_connections_notice: notice, connection_outcome: nil)
  end

  defp connection_outcome(%{"error" => "already-connected"}, _read),
    do: %{tone: :error, message: "That account is already connected to another account here."}

  defp connection_outcome(%{"error" => error}, _read) when is_binary(error) and error != "",
    do: %{tone: :error, message: "That connection couldn’t be verified. Try again."}

  defp connection_outcome(params, %Read{state: state, value: identities})
       when state in [:ready, :empty] do
    with {:ok, provider} <- Providers.parse(params["provider"]),
         {:ok, action} <- Map.fetch(@actions, params["action"]) do
      label = Providers.label(provider)

      case {action, Enum.any?(identities, &(&1.provider == provider))} do
        {:link, true} ->
          %{tone: :success, message: "#{label} connected."}

        {:link, false} ->
          %{tone: :error, message: "#{label} didn’t come back connected. Try again."}

        {:unlink, false} ->
          %{tone: :success, message: "#{label} disconnected."}

        {:unlink, true} ->
          %{tone: :error, message: "#{label} is still connected. Try again."}
      end
    else
      :error -> nil
    end
  end

  defp connection_outcome(_params, _read), do: nil
end
