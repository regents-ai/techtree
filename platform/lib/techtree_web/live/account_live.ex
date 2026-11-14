defmodule TechtreeWeb.AccountLive do
  @moduledoc """
  The signed-in person's Account, one tab each: Account (their profile, in the
  layout every Regent site shares, `Regent.Account.layout`, whose Public Display
  Name the page saves to their shared profile with its own sign-in),
  Agents (the agents they paired, whose Pair New Agent opens the pairing window),
  Wallets (the wallets their sign-in verified) and Connections (the accounts they
  have connected). Points has its own tab (`TechtreeWeb.PointsLive`).

  Everything here is read from the sign-in the shell already holds; nothing on
  the page asks the visitor to sign in again.
  """

  use TechtreeWeb, :html

  import TechtreeWeb.Components.VerifiedConnections

  attr :account, :map, default: nil
  attr :signed_out_reason, :atom, default: :signed_out
  attr :account_control, :map, required: true

  def profile(assigns) do
    ~H"""
    <.settings_page
      id="account-page"
      account={@account}
      signed_out_reason={@signed_out_reason}
    >
      <Regent.Account.layout id="account">
        <:identity>
          <Regent.Account.identity
            id="account-identity"
            name={@account_control.label}
            wallet={@account_control.wallet}
            ens_name={@account_control.ens_name}
          >
            <:picture>
              <TechtreeWeb.Components.AccountControls.account_picture
                id="account-identity-picture"
                squares={@account_control.squares}
                picture={@account_control.picture}
                size={64}
              />
            </:picture>
          </Regent.Account.identity>
        </:identity>
        <:profile>
          <%!-- The name is saved from the browser with the page's session and forms token. --%>
          <div id="account-profile" phx-hook="PublicName" phx-update="ignore">
            <Regent.Profile.panel
              id="account-public-name"
              class="account-panel"
              display_name={@account.display_name}
            />
          </div>
        </:profile>
      </Regent.Account.layout>
    </.settings_page>
    """
  end

  attr :lease, :map, required: true
  attr :account, :map, default: nil
  attr :signed_out_reason, :atom, default: :signed_out

  def agents(assigns) do
    ~H"""
    <.settings_page
      id="account-agents-page"
      account={@account}
      signed_out_reason={@signed_out_reason}
    >
      <.live_component
        module={TechtreeWeb.AgentsPanel}
        id="account-agents"
        lease={@lease}
        account={@account}
      />
    </.settings_page>
    """
  end

  attr :account, :map, default: nil
  attr :signed_out_reason, :atom, default: :signed_out

  def wallets(assigns) do
    ~H"""
    <.settings_page
      id="wallets-page"
      account={@account}
      signed_out_reason={@signed_out_reason}
    >
      <section class="account-panel account-details" aria-labelledby="account-wallets-title">
        <h2 id="account-wallets-title">Your wallets</h2>
        <dl>
          <div>
            <dt>Wallet</dt>
            <dd :if={@account.wallet_address} class="account-wallet">
              <code>{@account.wallet_address}</code>
              <Regent.Primitives.copy_button id="account-wallet-copy" text={@account.wallet_address}>
                Copy
              </Regent.Primitives.copy_button>
            </dd>
            <dd :if={is_nil(@account.wallet_address)}>No wallet linked</dd>
          </div>
          <div :if={other_wallets(@account) != []}>
            <dt>Linked wallets</dt>
            <dd>
              <ul class="account-wallet-list">
                <li :for={wallet <- other_wallets(@account)}><code>{wallet}</code></li>
              </ul>
            </dd>
          </div>
        </dl>
      </section>
    </.settings_page>
    """
  end

  attr :account, :map, default: nil
  attr :signed_out_reason, :atom, default: :signed_out
  attr :verified_connections, TechtreeWeb.Read, required: true
  attr :verified_connections_notice, :map, default: nil

  def connections(assigns) do
    ~H"""
    <.settings_page
      id="connections-page"
      account={@account}
      signed_out_reason={@signed_out_reason}
    >
      <.verified_connections
        id="account-verified-connections"
        class="account-panel"
        identities={@verified_connections.value}
        read_state={@verified_connections.state}
        notice={@verified_connections_notice}
      />
    </.settings_page>
    """
  end

  attr :id, :string, required: true
  attr :account, :map, default: nil
  attr :signed_out_reason, :atom, default: :signed_out
  slot :inner_block, required: true

  defp settings_page(assigns) do
    ~H"""
    <article id={@id} class="account-page rg-utility">
      <Regent.Account.signed_out
        :if={is_nil(@account)}
        id={"#{@id}-signed-out"}
        reason={@signed_out_reason}
      >
        <:sign_in>
          <Regent.Primitives.button type="button" data-account-target="sign-in">
            Sign in
          </Regent.Primitives.button>
        </:sign_in>
      </Regent.Account.signed_out>

      {@account && render_slot(@inner_block)}
    </article>
    """
  end

  defp other_wallets(%{wallet_address: primary, wallet_addresses: wallets}) do
    primary = primary && String.downcase(primary)

    wallets
    |> List.wrap()
    |> Enum.map(&String.downcase/1)
    |> Enum.uniq()
    |> Enum.reject(&(&1 == primary))
  end
end
