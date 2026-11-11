defmodule TechtreeWeb.Components.AccountControls do
  @moduledoc "The template account control and picture within Techtree’s frame."
  use TechtreeWeb, :html

  @doc "The `data-account-target` a wallet button carries: connect once signed in, sign in before."
  def account_target(%{kind: :signed_in}), do: "connect-wallet"
  def account_target(_account_control), do: "sign-in"

  attr :account_control, Techtree.AccessContext.AccountControl, required: true

  @doc """
  The account control at the right of the header on every page: Sign in, or,
  signed in, the picture and name, which open the account menu
  (`TechtreeWeb.AccountMenuLive`). auth_lazy.ts drives its `data-account-target`
  markers; the component itself never authenticates anyone.
  """
  def account_control(assigns) do
    ~H"""
    <div id="account-control" class="account-control" data-account-wallet={@account_control.wallet}>
      <Regent.Primitives.button
        :if={@account_control.kind == :sign_in}
        type="button"
        data-account-target="sign-in"
      >
        {@account_control.label}
      </Regent.Primitives.button>
      <button
        :if={@account_control.kind == :signed_in}
        id="account-chip"
        class="account-chip"
        type="button"
        popovertarget="account-menu"
      >
        <.account_name id="account-chip-picture" account_control={@account_control} />
      </button>
      <p
        id="account-auth-status"
        class="account-auth-status"
        role="status"
        aria-live="polite"
        aria-atomic="true"
        phx-update="ignore"
        hidden
      >
      </p>
    </div>
    """
  end

  attr :id, :string, required: true
  attr :account_control, Techtree.AccessContext.AccountControl, required: true

  # The account's picture and name. The `profile` marker tells the browser the
  # page was drawn for a signed-in account.
  defp account_name(assigns) do
    ~H"""
    <.account_picture
      id={@id}
      class="account-avatar"
      squares={@account_control.squares}
      picture={@account_control.picture}
      size={36}
    />
    <span
      class="account-name"
      data-account-target="profile"
    >
      {@account_control.label}
    </span>
    """
  end

  attr :id, :string, required: true
  attr :squares, :string, required: true, doc: "`Techtree.PublicIdentity.squares/1`"
  attr :picture, :string, required: true, doc: "`Techtree.PublicIdentity.picture/1`"
  attr :size, :integer, required: true
  attr :class, :string, default: nil

  @doc """
  An account's picture, wherever it is shown. The squares drawn from its wallet are there as soon
  as the page is; its ENS picture, which arrives from another website, lies
  over them and takes their place once it has arrived (`AccountPicture` in
  `assets/js/hooks/account_picture.ts`). A changed picture is a new element,
  so the squares show again while it arrives. Nothing is drawn for an account
  with no wallet.
  """
  def account_picture(assigns) do
    ~H"""
    <span
      :if={@squares}
      id={"#{@id}-#{:erlang.phash2(@picture)}"}
      class={["account-picture", @class]}
      phx-hook={@picture && "AccountPicture"}
    >
      <img src={@squares} width={@size} height={@size} alt="" />
      <img
        :if={@picture}
        src={@picture}
        referrerpolicy="no-referrer"
        width={@size}
        height={@size}
        alt=""
      />
    </span>
    """
  end
end
