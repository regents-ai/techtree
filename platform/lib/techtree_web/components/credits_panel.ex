defmodule TechtreeWeb.CreditsPanel do
  @moduledoc """
  The Buy Credits panel: the balance, the amount, the wallet presses
  and what each press did, all in one place. Built on the reference wallet
  component (`TechtreeWeb.OnchainExample`): the server builds the steps
  (`RegentCredits.Chains.steps/3`), every press goes straight to the wallet, and
  a confirmed Buy is reported once. Regents' Oban reconciles recorded purchases
  and discovers Base deposits even after this page closes. The panel only reads
  stored purchase state when the balance changes or the person refreshes.

  Credits are bought with USDC on Base only: the wallet is asked onto Base when
  a press needs it. The USDC of the wallet that pays is shown.

  Buy is disabled only when it is certain to fail, from the chain at the latest
  block: the Base approval does not cover the amount yet, or the wallet holds
  too little USDC. Explanations wait in tips; the panel shows figures, choices,
  presses and outcomes.

  The parent passes `account` (the signed-in account), its `credits` reading
  (`state` and the `RegentCredits.balance/1` value, kept current by the
  parent; the figures show only while it is `:ready`, and a dash otherwise), its
  `session_lease` as `lease` and `id`.
  """
  use TechtreeWeb, :live_component

  alias Regent.Primitives, as: P
  alias RegentChain.{Call, Presses, Review}
  alias RegentCredits.{Amount, Chains}
  alias Techtree.{AccessContext, ChainClient, Credits, Limits}
  alias TechtreeWeb.Live.Session
  alias TechtreeWeb.{OnchainSteps, Read}

  @impl true
  def mount(socket) do
    {:ok,
     socket
     |> Session.check_component_lease(&take_account/2)
     |> OnchainSteps.init()
     |> assign(
       active: nil,
       signer: nil,
       wallet: nil,
       amount: "5",
       number: Ecto.UUID.generate(),
       numbers: %{},
       usdc: nil,
       allowance: nil,
       latest: %{},
       purchases: %{},
       purchase_read: %Read{},
       reported: MapSet.new()
     )}
  end

  @impl true
  def update(%{account: account} = assigns, socket) do
    changed? = assigns.credits != socket.assigns[:credits]

    socket =
      socket
      |> assign(id: assigns.id, lease: assigns.lease, credits: assigns.credits)
      |> take_account(account)

    {:ok,
     if(changed? and assigns.credits.state == :ready, do: read_purchases(socket), else: socket)}
  end

  @impl true
  def handle_event("onchain_active_wallet", params, socket) do
    active = OnchainSteps.active_wallet(params)
    socket = if active == socket.assigns.active, do: socket, else: assign(socket, press_note: nil)
    {:noreply, socket |> assign(active: active) |> sync()}
  end

  def handle_event("change", %{"amount" => amount}, socket),
    do: {:noreply, socket |> assign(amount: amount) |> sync()}

  # The page asks when the panel opens, when it comes back into view and after
  # each press, so the funds behind a disabled Buy are read again then.
  def handle_event("refresh_funds", _params, socket),
    do: {:noreply, socket |> read_funds() |> read_purchases()}

  # A press made before the review caught up with the form: the form is taken
  # as the page's own, and the reply carries the review for it.
  def handle_event(
        "prepare_and_send",
        %{"form" => %{"amount" => amount}, "step" => name},
        socket
      )
      when is_binary(amount) do
    socket = socket |> assign(amount: amount) |> sync()

    case socket.assigns.review do
      %{} = review when is_binary(name) -> {:reply, %{review: review, send: name}, socket}
      _none -> {:reply, %{}, socket}
    end
  end

  def handle_event("step_sent", %{"transaction_hash" => hash} = params, socket)
      when is_binary(hash) do
    socket = OnchainSteps.sent(socket, params)

    {:noreply, socket}
  end

  def handle_event("step_failed", %{"reason" => reason}, socket) when is_binary(reason) do
    %{linked: linked, active: active, amount: amount} = socket.assigns
    TechtreeWeb.Telemetry.wallet_failed(:credits_panel, reason)

    note = amount_problem(amount) || OnchainSteps.failure_note(reason, linked, active, "Base")

    {:noreply, assign(socket, press_note: note)}
  end

  def handle_event("check_again", %{"hash" => hash}, socket),
    do: {:noreply, OnchainSteps.check_again(socket, hash)}

  def handle_event("check_purchase_again", _params, socket),
    do: {:noreply, read_purchases(socket)}

  @impl true
  # Wallet receipt observation is unchanged. Purchase reconciliation is never
  # called by its timer: only one report follows a confirmed Buy.
  def handle_async({:onchain_step, hash}, result, socket) do
    socket = socket |> OnchainSteps.checked(hash, result) |> approved(hash)

    case Enum.find(socket.assigns.presses.sent, &(&1.hash == hash)) do
      %{name: "buy", outcome: :confirmed, review: review} ->
        {:noreply, socket |> report_once(hash, review) |> read_funds()}

      %{outcome: outcome} when outcome in [:confirmed, :reverted] ->
        {:noreply, read_funds(socket)}

      _waiting ->
        {:noreply, socket}
    end
  end

  def handle_async({:report, owner, hash}, result, socket) do
    if owner == socket.assigns.account.privy_user_id do
      purchase =
        case result do
          {:ok, {:ok, purchase}} -> purchase
          _unavailable -> nil
        end

      {:noreply, socket |> put_purchase(hash, %{purchase: purchase}) |> read_purchases()}
    else
      {:noreply, socket}
    end
  end

  def handle_async({Read, :purchase_read, _generation} = name, result, socket) do
    socket = Read.settle(socket, name, result)

    {:noreply, show_purchases(socket, socket.assigns.purchase_read)}
  end

  # Each read answers with the wallet it was for, and lands only while that
  # wallet is still the one shown: the check before it can move the panel to
  # another. Only a figure read now may hold Buy back.
  def handle_async(figure, result, socket) when figure in [:usdc, :allowance] do
    case read(result, socket.assigns.wallet) do
      :other_wallet ->
        {:noreply, socket}

      :unread ->
        {:noreply, assign(socket, figure, :unread)}

      micro ->
        {:noreply,
         assign(socket, [{figure, micro}, latest: Map.put(socket.assigns.latest, figure, micro)])}
    end
  end

  defp show_purchases(socket, %{state: state, value: purchases}) when state in [:ready, :empty] do
    Enum.reduce(socket.assigns.presses.sent, socket, &show_purchase(&2, &1, purchases))
  end

  defp show_purchases(socket, _unavailable), do: socket

  defp show_purchase(socket, %{name: "buy", review: %{signer: wallet}, hash: hash}, purchases) do
    case Enum.find(purchases, &(&1.tx_hash == hash and &1.wallet == wallet)) do
      nil -> socket
      purchase -> put_purchase(socket, hash, %{purchase: purchase})
    end
  end

  defp show_purchase(socket, _other, _purchases), do: socket

  # A confirmed approval sets what staking may take to exactly its amount, so
  # the panel knows it from the receipt it just read, before the next read. It
  # is the shown wallet's figure only when that wallet sent it.
  defp approved(%{assigns: %{wallet: wallet}} = socket, hash) do
    case Enum.find(socket.assigns.presses.sent, &(&1.hash == hash)) do
      %{
        name: "approve",
        outcome: :confirmed,
        review: %{signer: ^wallet, inputs: %{"amount" => amount}}
      } ->
        assign(socket, allowance: Chains.micro(dollars(amount)))

      _other ->
        socket
    end
  end

  # The review follows the signer and the amount. A new amount is a new purchase
  # number; a repeat press of the same review buys again under the same number,
  # which is a second purchase.
  defp sync(socket) do
    %{linked: linked, active: active, amount: amount} = socket.assigns
    signer = OnchainSteps.signer(linked, active)
    dollars = dollars(amount)
    inputs = %{"amount" => amount}

    socket =
      if {inputs, signer} == {socket.assigns[:inputs], socket.assigns.signer},
        do: socket,
        else: assign(socket, inputs: inputs, number: Ecto.UUID.generate())

    review =
      if signer do
        steps =
          if dollars, do: Chains.steps(:base, dollars, socket.assigns.number), else: []

        Review.new(socket.assigns.id, signer, Chains.chain(:base), steps, inputs)
      end

    # A new amount changes no balance, so only a new wallet reads them.
    wallet = OnchainSteps.shown_wallet(linked, socket.assigns.own, active)

    socket =
      if wallet == socket.assigns.wallet,
        do: assign(socket, signer: signer),
        else:
          socket
          |> assign(signer: signer, wallet: wallet, usdc: nil, allowance: nil, latest: %{})
          |> read_funds()

    socket
    |> assign(mismatch: OnchainSteps.mismatch_note(linked, active))
    |> remember_number(review)
    |> OnchainSteps.put_review(review)
  end

  defp remember_number(socket, nil), do: socket

  defp remember_number(socket, review),
    do: assign(socket, numbers: Map.put(socket.assigns.numbers, review.id, socket.assigns.number))

  # Report once after the existing wallet observer confirms the receipt. A
  # refused/unavailable report is not retried here: Base's durable deposit
  # reader discovers it independently. This never resubmits a wallet action.
  defp report_once(socket, hash, review) do
    if MapSet.member?(socket.assigns.reported, hash) do
      socket
    else
      account = socket.assigns.account
      number = Map.fetch!(socket.assigns.numbers, review.id)

      socket
      |> assign(reported: MapSet.put(socket.assigns.reported, hash))
      |> put_purchase(hash, %{purchase: :reporting})
      |> start_async({:report, account.privy_user_id, hash}, fn ->
        send_report(account, review, number, hash)
      end)
    end
  end

  defp send_report(account, review, number, hash) do
    with :ok <- Limits.spend(:credits_report, {:human, account.id}) do
      RegentCredits.report_purchase(
        account.privy_user_id,
        review.signer,
        :base,
        dollars(review.inputs["amount"]),
        number,
        hash,
        actor: Credits.person(account)
      )
    end
  end

  # Only rows owned by the signed-in person, for this page's Base purchases.
  # Read owns generations and stale/error states; no chain call or ledger write.
  defp read_purchases(socket) do
    hashes = for %{name: "buy", hash: hash} <- socket.assigns.presses.sent, do: hash
    account = socket.assigns.account

    if hashes == [] do
      socket
    else
      Read.start(socket, :purchase_read, account.privy_user_id, fn ->
        Credits.stored_purchases(account, hashes)
      end)
    end
  end

  defp put_purchase(socket, hash, shown),
    do: assign(socket, purchases: Map.put(socket.assigns.purchases, hash, shown))

  # The shown wallet's USDC on Base, and what REGENT staking may take of it,
  # both at the latest block. The figures already shown stay on screen, but from
  # here until each new read lands none of them holds Buy back. Each account has
  # a read allowance; past it, a wallet not read yet shows them unavailable.
  defp read_funds(%{assigns: %{wallet: nil}} = socket), do: socket

  defp read_funds(socket) do
    %{usdc: usdc, allowance: allowance} = socket.assigns
    socket = assign(socket, latest: %{})

    case Limits.spend(:wallet_read, {:human, socket.assigns.account.id}) do
      :ok -> start_reads(socket)
      :limited -> assign(socket, usdc: usdc || :unread, allowance: allowance || :unread)
    end
  end

  defp start_reads(socket) do
    wallet = socket.assigns.wallet

    socket
    |> start_async(:usdc, fn -> {wallet, usdc_call("balanceOf(address)", [wallet])} end)
    |> start_async(:allowance, fn ->
      {wallet, usdc_call("allowance(address,address)", [wallet, Chains.staking()])}
    end)
  end

  defp read({:ok, {wallet, {:ok, micro}}}, wallet), do: micro
  defp read({:ok, {wallet, _unread}}, wallet), do: :unread
  defp read({:ok, {_other, _answer}}, _wallet), do: :other_wallet
  defp read({:exit, _reason}, _wallet), do: :unread

  defp usdc_call(signature, args) do
    call = %{to: Chains.usdc(:base), data: Call.encode(signature, args)}

    with {:ok, "0x" <> hex} <-
           ChainClient.rpc(Chains.chain(:base), "eth_call", [call, "latest"]) do
      {:ok, String.to_integer(hex, 16)}
    end
  end

  # The account as the page gave it, or as it reads now before each event and
  # each background result (`Session.check_component_lease/2`): the wallets that may act and the
  # review follow it.
  defp take_account(socket, account) do
    context = AccessContext.for_account(account)

    socket =
      if socket.assigns[:account] && socket.assigns.account.privy_user_id != account.privy_user_id do
        socket
        |> Read.clear(:purchase_read)
        |> OnchainSteps.init()
        |> assign(purchases: %{}, reported: MapSet.new(), numbers: %{})
      else
        socket
      end

    socket
    |> assign(
      account: account,
      linked: AccessContext.linked_wallets(context),
      own: AccessContext.own_wallet(context)
    )
    |> sync()
  end

  defp dollars(amount) do
    case Integer.parse(String.trim(amount)) do
      {n, ""} when n in 5..500 -> n
      _not_whole_dollars -> nil
    end
  end

  # Why an amount can't be bought, in words for the person; nil when it can.
  defp amount_problem(amount) do
    case Integer.parse(String.trim(amount)) do
      {n, ""} when n in 5..500 -> nil
      {n, ""} when n < 5 -> "The minimum is 5 USDC."
      {n, ""} when n > 500 -> "The maximum is 500 USDC per purchase."
      _not_whole -> "Enter a whole number from 5 to 500."
    end
  end

  @impl true
  def render(assigns) do
    dollars = dollars(assigns.amount)

    assigns =
      assign(assigns,
        dollars: dollars,
        problem: amount_problem(assigns.amount),
        approve: approve_step(assigns, dollars),
        buy: step(assigns, "buy"),
        blocked: blocked(assigns, dollars)
      )

    ~H"""
    <section id={@id} class="credits-panel" phx-hook="OnchainSteps" data-refresh-funds>
      <header class="credits-panel__head">
        <dl
          id={"#{@id}-figures"}
          class="credits-panel__figures"
          phx-hook="MotionCount"
          data-variant="flash"
        >
          <dt>Regents Credits</dt>
          <dd><span data-count>{figure(@credits, :available)}</span>{missing(@credits)}</dd>
          <dt>Active Bids</dt>
          <dd><span data-count>{figure(@credits, :held)}</span>{missing(@credits)}</dd>
        </dl>
        <a
          class="credits-panel__history"
          href="https://regents.sh/account/credits"
          target="_blank"
          rel="noopener"
        >
          Purchase History
        </a>
      </header>

      <form
        id={"#{@id}-form"}
        class="credits-panel__form"
        phx-change="change"
        phx-submit="change"
        phx-target={@myself}
      >
        <label class="credits-panel__label" for={"#{@id}-amount"}>USDC on Base</label>
        <div class="credits-panel__amount" data-invalid={@problem && "true"}>
          <input
            id={"#{@id}-amount"}
            name="amount"
            value={@amount}
            inputmode="numeric"
            autocomplete="off"
            aria-describedby={"#{@id}-rate #{@id}-problem"}
            aria-invalid={@problem && "true"}
            data-onchain-input="amount"
          />
          <span aria-hidden="true">USDC</span>
        </div>
        <p id={"#{@id}-rate"} class="credits-panel__rate">
          Regents Credits can be used across all Regents sites. See them on
          <a href="https://regents.sh">regents.sh</a>
        </p>
        <p
          id={"#{@id}-problem"}
          class="credits-panel__problem"
          role="alert"
          phx-hook="MotionRefusal"
          data-refused
        >
          {@problem}
        </p>
      </form>

      <%!-- Lines above the buttons stay in the page with their room kept, so one
           appearing never moves or replaces the button a person is about to press. --%>
      <div class="credits-panel__wallet" data-empty={is_nil(@wallet)}>
        <span class="credits-panel__muted">{if @signer, do: "Paying from", else: "Wallet"}</span>
        <code>{@wallet && RegentFormat.short_address(@wallet)}</code>
        <span class="credits-panel__usdc">{usdc(@usdc)}</span>
      </div>
      <p class="credits-panel__note credits-panel__mismatch">{@mismatch}</p>

      <ol class="credits-panel__steps">
        <li class="credits-panel__step" data-state={@approve.state}>
          <P.button variant="secondary" data-onchain-step="approve">
            <span data-press-label>Approve</span>
          </P.button>
          <div class="credits-panel__step-words">
            <strong>
              Approve {@dollars && "#{@dollars} "}USDC
              <P.tip id={"#{@id}-approve-tip"} label="About approving">
                Lets REGENT staking take this USDC for your purchase. Each purchase needs its own approval.
              </P.tip>
            </strong>
            <span :if={@approve.words}>{@approve.words}</span>
          </div>
          <.check_again step={@approve} myself={@myself} />
        </li>
        <li class="credits-panel__step" data-state={@buy.state}>
          <P.button
            data-onchain-step="buy"
            disabled={@blocked != nil}
            aria-describedby={@blocked && "#{@id}-buy-why"}
          >
            <span data-press-label>Buy</span>
          </P.button>
          <div class="credits-panel__step-words">
            <strong>
              Buy {@dollars && "#{@dollars} "}Credits
              <P.tip id={"#{@id}-buy-tip"} label="About buying">
                Sends the USDC to REGENT staking. Credits usually arrive after confirmation. Automatic discovery can take about 10 minutes or longer if the network is unavailable.
              </P.tip>
            </strong>
            <span :if={@buy.words}>{@buy.words}</span>
            <span :if={@buy.help?}>
              If USDC left your wallet, post the link in <a
                href="https://patchbay.help/credits-help"
                target="_blank"
                rel="noopener"
              >Credits help</a>.
            </span>
            <span :if={@blocked} id={"#{@id}-buy-why"}>{@blocked}</span>
          </div>
          <.check_again step={@buy} myself={@myself} />
        </li>
      </ol>

      <%!-- Room for three lines is kept, so a note never moves the links below. --%>
      <div class="credits-panel__press-notes">
        <p :if={@purchase_read.state in [:error, :stale]} class="credits-panel__note" role="status">
          Purchase status is unavailable. Refresh to read it again; background processing continues.
        </p>
        <p :if={@press_note} class="credits-panel__note" role="status">{@press_note}</p>
        <p class="credits-panel__note" role="status" data-onchain-lost hidden>
          Connection lost, so nothing was sent. Press again once it's back.
        </p>
      </div>

      <footer class="credits-panel__legal">
        <a href="https://regents.sh/terms" target="_blank" rel="noopener">Terms of Service</a>
        <a href="https://regents.sh/credits/refunds" target="_blank" rel="noopener">
          Refund Policy
        </a>
      </footer>
    </section>
    """
  end

  attr(:step, :map, required: true)
  attr(:myself, :any, required: true)

  defp check_again(%{step: %{entry: entry, stalled?: true}} = assigns) do
    assigns = assign(assigns, event: check_event(entry), hash: entry.hash)

    ~H"""
    <P.button
      variant="quiet"
      class="credits-panel__again"
      phx-click={@event}
      phx-value-hash={@hash}
      phx-target={@myself}
    >
      Check again
    </P.button>
    """
  end

  defp check_again(assigns), do: ~H""

  defp check_event(%{name: "buy", outcome: :confirmed}), do: "check_purchase_again"
  defp check_event(_entry), do: "check_again"

  # The latest press of the named step for the form as it stands now: its state
  # (`:ready` before any), what it did in words, and whether it waits on a
  # Check again.
  defp step(assigns, name) do
    %{presses: %{sent: sent}, purchases: purchases, inputs: inputs} = assigns

    case Enum.find(sent, &(&1.name == name and match?(%{inputs: ^inputs}, &1.review))) do
      nil ->
        %{state: :ready, words: nil, help?: false, entry: nil, stalled?: false}

      entry ->
        shown = purchases[entry.hash]

        %{
          state: step_state(state(entry, shown)),
          words: words(entry, shown),
          help?: help?(shown),
          entry: entry,
          stalled?: stalled?(entry, shown)
        }
    end
  end

  # Approve shows what the chain says staking may take: done while that covers
  # the amount, whichever press made it so, and ready again once a Buy spends it.
  defp approve_step(assigns, dollars) do
    step = step(assigns, "approve")

    cond do
      step.state == :pending -> step
      covered?(assigns.allowance, dollars) -> %{step | state: :done, words: nil}
      step.state == :done -> %{step | state: :ready, words: nil}
      true -> step
    end
  end

  defp covered?(allowance, dollars) when is_integer(allowance) and is_integer(dollars),
    do: allowance >= Chains.micro(dollars)

  defp covered?(_allowance, _dollars), do: false

  # Why Buy is certain to fail right now, from the shown wallet's last read at
  # the latest block; nil when it may go through. A figure still being read,
  # unread or past the read allowance is never a reason.
  defp blocked(_assigns, nil), do: nil

  defp blocked(%{latest: latest}, dollars) do
    micro = Chains.micro(dollars)

    cond do
      is_integer(latest[:usdc]) and latest.usdc < micro ->
        "Send USDC on Base to your wallet address first"

      is_integer(latest[:allowance]) and latest.allowance < micro ->
        "Approve first"

      true ->
        nil
    end
  end

  defp step_state(state) when state in [:confirmed, :credited], do: :done
  defp step_state(state) when state in [:pending, :checking, :stalled], do: :pending
  defp step_state(_failed), do: :failed

  defp stalled?(%{name: "buy"}, %{} = shown), do: purchase_stalled?(shown)
  defp stalled?(entry, nil), do: Presses.stalled?(entry)
  defp stalled?(_entry, _shown), do: false

  # Until the balance is read, or when it can't be, each figure is a dash, as
  # in the header; a word beside it would wrap on a phone and move the buttons.
  # Only a balance just read shows; while it is read again, or when it can't be,
  # each figure is a dash.
  defp figure(%{state: :ready, value: balance}, field),
    do: balance |> Map.fetch!(field) |> Amount.format() |> String.replace_suffix(" Credits", "")

  defp figure(_credits, _field), do: "—"

  defp missing(%{state: :ready}), do: nil

  defp missing(%{state: state} = assigns) when state in [:error, :stale],
    do: ~H|<span class="visually-hidden">Unavailable</span>|

  defp missing(assigns), do: ~H|<span class="visually-hidden">Loading</span>|

  defp state(entry, nil), do: OnchainSteps.describe(entry, chain_name_of(entry)).state
  defp state(_entry, %{purchase: :reporting}), do: :checking
  defp state(_entry, %{purchase: nil}), do: :checking
  defp state(_entry, %{purchase: purchase}), do: purchase.status

  # A step on its way or done shows as a mark; only trouble needs words.
  defp words(entry, nil) do
    case OnchainSteps.describe(entry, chain_name_of(entry)) do
      %{state: :pending} -> "Waiting for #{chain_name_of(entry)}"
      %{state: :confirmed} -> nil
      %{words: words} -> words
    end
  end

  defp words(entry, %{purchase: :reporting}), do: "Waiting for #{chain_name_of(entry)}"

  defp words(_entry, %{purchase: nil}),
    do:
      "Confirmed on Base. Automatic credit discovery can take about 10 minutes or longer; you can close this page."

  defp words(_entry, %{purchase: purchase}) do
    case purchase do
      %{status: :credited, amount: amount} ->
        "#{Amount.format(amount)} added"

      %{status: :failed, reason: "reverted"} ->
        "Didn't go through. Nothing moved."

      %{status: :failed, reason: "already credited"} ->
        "Already counted."

      %{status: :failed, reason: "not found"} ->
        "Base never showed this payment. No Credits added."

      %{status: :failed} ->
        "Not the purchase this page prepared. No Credits added."

      %{status: :checking} ->
        "Payment recorded. Background processing continues even if you close this page."
    end
  end

  defp help?(%{purchase: %{status: :failed, reason: reason}}),
    do: reason not in ["reverted", "already credited", "not found"]

  defp help?(_shown), do: false

  defp purchase_stalled?(%{purchase: nil}), do: true
  defp purchase_stalled?(%{purchase: %{status: :checking}}), do: true
  defp purchase_stalled?(_shown), do: false

  defp chain_name_of(%{review: %{chain: %{name: name}}}), do: name
  defp chain_name_of(_unknown), do: "the network"

  defp usdc(nil), do: "…"
  defp usdc(:unread), do: "unavailable"

  defp usdc(micro) do
    dollars = micro |> Decimal.new() |> Decimal.div(1_000_000) |> Decimal.round(2, :down)
    "#{Decimal.to_string(dollars, :normal)} USDC"
  end
end
