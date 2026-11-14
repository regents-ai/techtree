defmodule TechtreeWeb.AccountShellLive do
  @moduledoc "One template account frame for profile, agents, Points, wallets and connections."
  use TechtreeWeb, :live_view

  alias Techtree.{Accounts, SharedReading}
  alias Techtree.Accounts.LinkedIdentity.Providers
  alias Techtree.Actors.Human
  alias Techtree.Points.Board
  alias TechtreeWeb.{AccountLive, Read}

  import TechtreeWeb.Components.Marketing, only: [opening: 1]

  @tabs [
    %{route_id: :account, label: "Account", path: "/account", line: "Your profile."},
    %{
      route_id: :account_agents,
      label: "Agents",
      path: "/account/agents",
      line: "The agents you paired."
    },
    %{
      route_id: :points,
      label: "Points",
      path: "/account/points",
      line: "One total for you and your agents."
    },
    %{
      route_id: :wallets,
      label: "Wallets",
      path: "/account/wallets",
      line: "The wallets your sign-in verified."
    },
    %{
      route_id: :connections,
      label: "Connections",
      path: "/account/connections",
      line: "Accounts you have connected, such as X, GitHub and Farcaster."
    }
  ]
  @actions %{"link" => :link, "unlink" => :unlink}
  @refused %{
    tone: :error,
    message: "That connection couldn’t be updated. Refresh the page and try again."
  }

  # The Points total rolls only for a change made after this connection's first
  # render (`:points_rolls`), so a total that changed while the page was away,
  # before a reconnect, is simply there.
  @impl true
  def mount(_params, _session, socket) do
    if connected?(socket) do
      subscribe_to_own_topics(socket.assigns.access_context)
      send(self(), :points_rolls)
    end

    {:ok,
     socket
     |> assign(
       tabs: @tabs,
       hearing_board?: false,
       verified_connections: %Read{},
       points: %Read{},
       points_bonus: %Read{},
       points_board: %Read{},
       points_earning: [],
       points_rolls?: false,
       verified_connections_notice: nil,
       connection_outcome: nil
     )}
  end

  @impl true
  def handle_params(_params, _uri, socket) do
    route_spec = Enum.find(@tabs, &(&1.route_id == socket.assigns.live_action))

    {:noreply,
     socket
     |> assign(page_title: route_spec.label, route_spec: route_spec)
     |> hear_board(route_spec)
     |> load_points(route_spec)
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

  # The Account page saved the person's Public Display Name in their shared
  # profile. Every event reads the account again first (`TechtreeWeb.Live.Session`),
  # so this page already shows the new name; the account's topic tells its other
  # live pages, the account menu beside this one among them, to read it again too.
  def handle_event("public_name_saved", _params, socket) do
    with %{id: id} <- current_account(socket.assigns.access_context) do
      TechtreeWeb.Endpoint.broadcast(Accounts.HumanAccount.topic(id), "public_name_saved", %{})
    end

    {:noreply, socket}
  end

  @impl true
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

  # The board every signed-in reader shares was read again.
  def handle_info(
        {:shared_reading, {:points_board, _program}},
        %{assigns: %{route_spec: %{route_id: :points}}} = socket
      ),
      do: {:noreply, read_points_board(socket)}

  def handle_info({:shared_reading, {:points_board, _program}}, socket), do: {:noreply, socket}

  def handle_info(:points_rolls, socket), do: {:noreply, assign(socket, points_rolls?: true)}

  # An agent paired, checked in or was unpaired, here or on another Regent site.
  # The Agents tab lists the agents; the account menu and the pairing window
  # follow on their own.
  def handle_info(:agents_changed, socket) do
    if socket.assigns.route_spec.route_id == :account_agents,
      do: send_update(TechtreeWeb.AgentsPanel, id: "account-agents", agents_changed: true)

    {:noreply, socket}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide flush>
      <div
        id="account-shell"
        class="account-shell"
        phx-hook="AccountShell"
        data-destination={@route_spec.path}
        data-variant={TechtreeWeb.Motion.standard("tabs")}
      >
        <.opening
          eyebrow="Account"
          title={@route_spec.label}
          line={@route_spec.line}
          rise={false}
          book_call={false}
        >
          <nav class="account-shell__tabs" aria-label="Account views" data-shell-nav>
            <.link
              :for={tab <- @tabs}
              patch={tab.path}
              aria-current={@route_spec.route_id == tab.route_id && "page"}
            >
              {tab.label}
            </.link>
          </nav>
        </.opening>
        <div id="route-content" class="account-shell__body">
          <AccountLive.profile
            :if={@route_spec.route_id == :account}
            signed_out_reason={@signed_out_reason}
            account={current_account(@access_context)}
            account_control={@account_control}
          />
          <AccountLive.agents
            :if={@route_spec.route_id == :account_agents}
            signed_out_reason={@signed_out_reason}
            lease={@session_lease}
            account={current_account(@access_context)}
          />
          <TechtreeWeb.PointsLive.page
            :if={@route_spec.route_id == :points}
            signed_out_reason={@signed_out_reason}
            account={current_account(@access_context)}
            points={@points}
            board={@points_board}
            bonus={@points_bonus}
            earning={@points_earning}
            rolls?={@points_rolls?}
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
        </div>
      </div>
    </Layouts.page>
    """
  end

  defp subscribe_to_own_topics(%{principal: {:human, account}}) do
    Phoenix.PubSub.subscribe(Techtree.PubSub, "points:#{account.id}")
    Phoenix.PubSub.subscribe(Techtree.PubSub, RegentAgents.topic(account.privy_user_id))
  end

  defp subscribe_to_own_topics(_access_context), do: :ok

  # The page hears the shared Points board while the Points page is open, and
  # not elsewhere.
  defp hear_board(socket, %{route_id: route}) do
    hearing? = socket.assigns.hearing_board?
    wanted? = route == :points

    if connected?(socket) and hearing? != wanted? do
      if wanted?,
        do: SharedReading.subscribe(Board.key()),
        else: SharedReading.unsubscribe(Board.key())

      assign(socket, :hearing_board?, wanted?)
    else
      socket
    end
  end

  defp current_account(%{principal: {:human, account}}), do: account
  defp current_account(_access_context), do: nil

  defp human_actor(%{assigns: %{access_context: %{principal: {:human, account}}}}),
    do: Human.for_account(account)

  defp human_actor(_socket), do: nil

  # The NFT tier is read from Base once per page open, never on each award
  # notice, and not at all while nothing earns.
  defp load_points(socket, %{route_id: :points}) do
    socket
    |> assign(:points_earning, RegentPoints.Rules.active())
    |> read_points()
    |> read_points_board()
    |> read_points_bonus()
  end

  defp load_points(socket, _),
    do: socket |> Read.clear(:points) |> Read.clear(:points_board) |> Read.clear(:points_bonus)

  defp read_points(socket) do
    case human_actor(socket) do
      %Human{} = actor ->
        Read.now(socket, :points, actor.human_account_id, fn ->
          RegentPoints.summary(actor: actor)
        end)

      nil ->
        Read.clear(socket, :points)
    end
  end

  # The board every signed-in reader shares (Techtree.Points.Board). The
  # reader's own row and place are found from it, and their own total, as the
  # page renders.
  defp read_points_board(socket) do
    case human_actor(socket) do
      %Human{} -> assign(socket, :points_board, board_read(SharedReading.fetch(Board.key())))
      nil -> Read.clear(socket, :points_board)
    end
  end

  # Loading until the board is first read, an error when that first read failed,
  # and behind while the last read failed.
  defp board_read(:error), do: %Read{state: :loading}
  defp board_read({:ok, %{reading: nil}}), do: %Read{state: :error, error: :not_read}

  defp board_read({:ok, %{reading: board, at: at, degraded?: true}}),
    do: %Read{state: :stale, value: board, read_at: at, error: :not_read}

  defp board_read({:ok, %{reading: board, at: at}}),
    do: %Read{state: :ready, value: board, read_at: at}

  defp read_points_bonus(%{assigns: %{points_earning: []}} = socket),
    do: Read.clear(socket, :points_bonus)

  defp read_points_bonus(socket) do
    case human_actor(socket) do
      %Human{human_account_id: id} ->
        Read.start(socket, :points_bonus, id, fn -> points_bonus(id) end)

      nil ->
        Read.clear(socket, :points_bonus)
    end
  end

  # Base is read for the person's NFTs, counted against the account's own
  # allowance for wallet reads.
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
