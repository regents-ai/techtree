defmodule TechtreeWeb.Components.AccountControls do
  @moduledoc "The template account control and picture within Techtree’s frame."
  use TechtreeWeb, :html

  @doc "The `data-account-target` a wallet button carries: connect once signed in, sign in before."
  def account_target(%{kind: :signed_in}), do: "connect-wallet"
  def account_target(_account_control), do: "sign-in"

  attr :account_control, Techtree.AccessContext.AccountControl, required: true

  @doc """
  The account control at the right of the header on every page: Sign in, or,
  signed in, the name, which opens the side panel. auth_lazy.ts drives its
  `data-account-target` markers; the component itself never authenticates anyone.
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
        aria-controls="shell-aside"
        aria-expanded="false"
        data-aside-toggle
        phx-mounted={JS.ignore_attributes(["aria-expanded"])}
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

  attr :credits, TechtreeWeb.Read, required: true

  def credits_control(assigns) do
    ~H"""
    <button
      :if={@credits}
      id="shell-credits-button"
      class="shell-credits"
      type="button"
      aria-haspopup="dialog"
      aria-controls="shell-credits"
      aria-label={credits_label(@credits)}
      data-credits-open
      phx-hook="MotionCount"
      data-variant="flash"
    >
      <.credits_amount amount={@credits} />
    </button>
    """
  end

  defp credits_label(%{state: :ready, value: balance}),
    do: RegentCredits.Amount.format(balance.available)

  defp credits_label(%{state: state}) when state in [:error, :stale], do: "Credits unavailable"
  defp credits_label(_reading), do: "Credits loading"

  attr :amount, :map, required: true

  # "12.40 Credits", whose unit a phone's header leaves out for room. Only a
  # balance just read shows; while it is read again, or when it can't be, the
  # figure is a dash. The button and the Buy Credits panel behind it are there
  # either way.
  defp credits_amount(%{amount: %{state: :ready, value: balance}} = assigns) do
    [number, unit] = String.split(RegentCredits.Amount.format(balance.available), " ", parts: 2)
    assigns = assign(assigns, number: number, unit: unit)

    ~H"""
    <span data-count>{@number}</span> <span class="shell-credits__unit">{@unit}</span>
    """
  end

  defp credits_amount(assigns) do
    ~H"""
    <span data-count>—</span> <span class="shell-credits__unit">Credits</span>
    """
  end
end
