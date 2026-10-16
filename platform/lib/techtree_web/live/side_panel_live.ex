defmodule TechtreeWeb.SidePanelLive do
  @moduledoc """
  The account control at the right of the header and the side panel it opens, on
  every page. The root layout renders it beside the page's own LiveView, so it
  stays as it is while the person moves between pages.

  Signed out, it is the Sign in button. Signed in, it is the person's name, which
  opens the panel: Sign out, Manage Account on regents.sh and the Techtree
  account, then the agents paired with the account (`TechtreeWeb.PanelAgents`)
  with where each was last active, and Pair New Agent (`TechtreeWeb.PairingBox`). Whether the panel is open is the
  browser's (`assets/js/side_panel.ts` and the `techtree_aside` cookie, read into
  `<html data-aside>`), so the server never stores it.
  """
  use TechtreeWeb, :live_view

  import TechtreeWeb.Components.AccountControls, only: [account_control: 1]

  on_mount {TechtreeWeb.Live.Session, :load_human}

  @impl true
  def mount(_params, _session, socket) do
    if connected?(socket), do: subscribe_to_agents(socket.assigns.access_context)

    {:ok, socket, layout: false}
  end

  # An agent paired, checked in or was unpaired, here or on another Regent site.
  @impl true
  def handle_info(:agents_changed, socket) do
    send_update(TechtreeWeb.PanelAgents, id: "shell-agents", agents_changed: true)
    send_update(TechtreeWeb.PairingBox, id: "shell-pairing-box", agents_changed: true)

    {:noreply, socket}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <div id="side-panel-control" class="side-panel" phx-hook="SidePanel">
      <.account_control account_control={@account_control} />
      <aside
        :if={current_account(@access_context)}
        id="shell-aside"
        aria-label="Your account and agents"
        tabindex="-1"
      >
        <div class="shell-aside__head">
          <Regent.Primitives.button
            variant="secondary"
            type="button"
            data-account-target="sign-out"
          >
            Sign out
          </Regent.Primitives.button>
          <a
            href="https://regents.sh/account"
            class="rg-button rg-button--secondary"
            target="_blank"
            rel="noopener noreferrer"
          >
            Manage Account
          </a>
          <a href={~p"/account"} class="rg-button rg-button--secondary">Techtree account</a>
        </div>

        <.live_component
          module={TechtreeWeb.PanelAgents}
          id="shell-agents"
          lease={@session_lease}
          account={current_account(@access_context)}
        />

        <section id="shell-pairing" aria-labelledby="shell-pairing-title">
          <h2 id="shell-pairing-title">Pair New Agent</h2>
          <.live_component
            module={TechtreeWeb.PairingBox}
            id="shell-pairing-box"
            lease={@session_lease}
            account={current_account(@access_context)}
          />
        </section>
      </aside>
    </div>
    """
  end

  defp subscribe_to_agents(%{principal: {:human, account}}),
    do: Phoenix.PubSub.subscribe(Techtree.PubSub, RegentAgents.topic(account.privy_user_id))

  defp subscribe_to_agents(_access_context), do: :ok

  defp current_account(%{principal: {:human, account}}), do: account
  defp current_account(_access_context), do: nil
end
