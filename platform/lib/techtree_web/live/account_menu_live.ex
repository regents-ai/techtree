defmodule TechtreeWeb.AccountMenuLive do
  @moduledoc """
  The account control at the right of the header and the account menu it opens,
  on every page. The root layout renders it beside the page's own LiveView, so it
  stays as it is while the person moves between pages.

  Signed out, it is the Sign in button. Signed in, it is the person's picture and
  name, which open the account menu (`Regent.Account.menu`) hanging under it: the
  person's picture, name and wallet, the three agents paired with the account that
  were active most recently (`TechtreeWeb.MenuAgents`), Pair New Agent, Manage
  Account and Sign out. Pairing itself and everything else about the account are
  on the Account page. The browser opens and closes the menu (`popover`), so the
  server never stores whether it is open; following a link in it closes it
  (`assets/js/hooks/account_menu.ts`).
  """
  use TechtreeWeb, :live_view

  import TechtreeWeb.Components.AccountControls, only: [account_control: 1, account_picture: 1]

  on_mount {TechtreeWeb.Live.Session, :load_visitor}

  @impl true
  def mount(_params, _session, socket) do
    if connected?(socket), do: subscribe_to_agents(socket.assigns.access_context)

    {:ok, socket, layout: false}
  end

  # An agent paired, checked in or was unpaired, here or on another Regent site.
  @impl true
  def handle_info(:agents_changed, socket) do
    send_update(TechtreeWeb.MenuAgents, id: "shell-agents", agents_changed: true)

    {:noreply, socket}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <div id="account-menu-control" class="account-menu-control" phx-hook="AccountMenu">
      <.account_control account_control={@account_control} />
      <Regent.Account.menu
        :if={current_account(@access_context)}
        id="account-menu"
        name={@account_control.label}
        wallet={@account_control.wallet}
        ens_name={@account_control.ens_name}
        manage_href={~p"/account"}
        pair_href={~p"/account#account-pairing"}
      >
        <:picture>
          <.account_picture
            id="account-menu-picture"
            squares={@account_control.squares}
            picture={@account_control.picture}
            size={40}
          />
        </:picture>
        <:agents>
          <.live_component
            module={TechtreeWeb.MenuAgents}
            id="shell-agents"
            lease={@session_lease}
            account={current_account(@access_context)}
          />
        </:agents>
      </Regent.Account.menu>
    </div>
    """
  end

  defp subscribe_to_agents(%{principal: {:human, account}}),
    do: Phoenix.PubSub.subscribe(Techtree.PubSub, RegentAgents.topic(account.privy_user_id))

  defp subscribe_to_agents(_access_context), do: :ok

  defp current_account(%{principal: {:human, account}}), do: account
  defp current_account(_access_context), do: nil
end
