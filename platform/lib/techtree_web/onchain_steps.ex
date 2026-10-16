defmodule TechtreeWeb.OnchainSteps do
  @moduledoc """
  The server half of a wallet-button component. `skills/onchain-buttons` has the
  rules; `TechtreeWeb.OnchainExample` uses every function here.

  The component builds a `RegentChain.Review` for the eligible signer and hands
  it to `put_review/2`, which pushes it to the page before anyone presses. The
  page reports each press against the review it sent from, and every sent step
  is then read at the latest block of the review's chain, every quarter second,
  until it lands or the page stops asking. Nothing is kept beyond the page.

  The only wallet that may act is Privy's active wallet when it is one of the
  signed-in account's own (`signer/2`).
  """

  import Phoenix.Component, only: [assign: 2]
  import Phoenix.LiveView, only: [push_event: 3, start_async: 3]

  alias RegentChain.{Outcome, Presses}
  alias Techtree.ChainClient

  @recheck_ms 250
  @address ~r/\A0x[0-9a-fA-F]{40}\z/
  @no_wallet "Your account has no wallet yet. Sign in again to get one."

  @doc "The assigns a wallet-button component starts with."
  def init(socket), do: assign(socket, presses: Presses.new(), review: nil, press_note: nil)

  @doc """
  The wallet that may act: Privy's `active` wallet when the signed-in account
  links it, lowercased. Signed out (`linked` is `nil`), with no active wallet, or
  with one the account does not link, nothing may act.
  """
  def signer(nil, _active), do: nil
  def signer(_linked, nil), do: nil

  def signer(linked, active) do
    active = String.downcase(active)
    if active in Enum.map(linked, &String.downcase/1), do: active
  end

  @doc """
  The wallet a panel shows figures for. Signed in, the wallet that may act, or
  with none the account's own wallet (`own`), so a wrong or missing active wallet
  never empties the panel. Signed out (`linked` is `nil`), Privy's active wallet.
  """
  def shown_wallet(nil, _own, active), do: active
  def shown_wallet(linked, own, active), do: signer(linked, active) || own

  @doc "Privy's active wallet as the page reported it, or `nil`."
  def active_wallet(%{"address" => address}) when is_binary(address) do
    if Regex.match?(@address, address), do: String.downcase(address)
  end

  def active_wallet(_params), do: nil

  @doc """
  Puts `review` (or none) on the page when it is not the one already there. A
  review is fixed once built, so a new signer, chain or figure is a new review,
  and the page drops the old one as soon as this arrives.
  """
  def put_review(%{assigns: %{review: nil}} = socket, nil), do: socket
  def put_review(%{assigns: %{review: %{id: id}}} = socket, %{id: id}), do: socket

  def put_review(socket, review) do
    presses =
      if review,
        do: Presses.remember(socket.assigns.presses, review),
        else: socket.assigns.presses

    socket
    |> assign(review: review, presses: presses)
    |> push_event("onchain-steps:review", %{component_id: socket.assigns.id, review: review})
  end

  @doc "The wallet sent a step; it is read from now on against the review it was sent from."
  def sent(socket, params) do
    case Presses.sent(socket.assigns.presses, params) do
      {:ok, entry, presses} -> socket |> assign(presses: presses, press_note: nil) |> check(entry)
      :error -> socket
    end
  end

  @doc """
  The wallet signed a step: `{:ok, signed, socket}` with the server's own typed
  data and the signature, for the component to hand on.
  """
  def signed(socket, params) do
    case Presses.signed(socket.assigns.presses, params) do
      {:ok, signed} -> {:ok, signed, assign(socket, press_note: nil)}
      :error -> :error
    end
  end

  @doc "Starts reading a step again after the page stopped on its own."
  def check_again(socket, hash) do
    case Presses.check_again(socket.assigns.presses, hash) do
      {nil, _presses} -> socket
      {entry, presses} -> socket |> assign(presses: presses) |> check(entry)
    end
  end

  @doc "One answer from `handle_async({:onchain_step, hash}, result, socket)`."
  def checked(socket, hash, {:exit, _reason}), do: checked(socket, hash, {:ok, :unanswered})

  def checked(socket, hash, {:ok, answer}) do
    case Presses.checked(socket.assigns.presses, hash, answer) do
      {nil, _presses} ->
        socket

      {entry, presses} ->
        socket = assign(socket, presses: presses)
        if Presses.reading?(entry), do: check(socket, entry), else: socket
    end
  end

  @doc """
  What to say when a press sent nothing, or may have sent something, in words
  for the person who pressed. `linked` and `active` are the account's wallets
  (`nil` signed out) and Privy's active wallet, as for `signer/2`.
  """
  def failure_note(reason, nil, _active, _chain_name)
      when reason in ~w(step_unknown wallet_unavailable),
      do: "Sign in to send this. Nothing was sent."

  def failure_note(reason, [], _active, _chain_name)
      when reason in ~w(step_unknown wallet_unavailable),
      do: "#{@no_wallet} Nothing was sent."

  def failure_note(reason, linked, nil, _chain_name)
      when reason in ~w(step_unknown wallet_unavailable),
      do:
        "You're signed in with #{wallets(linked, " and ")}, but your wallet app has no wallet open. Open #{wallets(linked, " or ")} there, then press again. Nothing was sent."

  def failure_note(reason, linked, active, _chain_name)
      when reason in ~w(step_unknown wallet_unavailable) do
    cond do
      signer(linked, active) == nil ->
        "#{mismatch_note(linked, active)} Nothing was sent."

      reason == "step_unknown" ->
        "This can't be sent as it stands. Check the details above, then press again. Nothing was sent."

      true ->
        "Your wallet changed during the press, so nothing was sent. Press again."
    end
  end

  def failure_note("network_mismatch", _linked, _active, chain_name),
    do:
      "Your wallet is on a different network. Switch it to #{chain_name}, then press again. Nothing was sent."

  def failure_note("wallet_declined", _linked, _active, _chain_name),
    do: "Your wallet declined this. Nothing was sent."

  def failure_note("insufficient_funds", _linked, _active, chain_name),
    do:
      "Your wallet doesn't have enough on #{chain_name} to pay the network fee. Nothing was sent."

  def failure_note("send_unconfirmed", _linked, _active, _chain_name),
    do: "Your wallet may have sent this. Check your wallet activity."

  @doc """
  The note beside the buttons while the wallet app has open a wallet the
  signed-in account does not link, naming both and asking the person to switch.
  """
  def mismatch_note([], active) when is_binary(active), do: @no_wallet

  def mismatch_note(linked, active) when is_list(linked) and is_binary(active) do
    if signer(linked, active) == nil do
      "Your wallet is on #{short(active)}, which isn't linked to this account. Switch to #{wallets(linked, " or ")}."
    end
  end

  def mismatch_note(_linked, _active), do: nil

  @doc """
  One sent step as the page shows it: its state and generic words. A component
  names its steps and may say more about them.
  """
  def describe(entry, chain_name) do
    state = if Presses.stalled?(entry), do: :stalled, else: entry.outcome
    %{hash: entry.hash, state: state, words: words(state, chain_name)}
  end

  defp words(:pending, chain_name), do: "Sent. Waiting for #{chain_name}."

  defp words(:stalled, chain_name),
    do: "#{chain_name} has not confirmed this yet. Check again, or look in your wallet activity."

  defp words(:confirmed, _chain_name), do: "Done."
  defp words(:reverted, _chain_name), do: "This did not go through and nothing moved."

  defp words(_not_this_step, _chain_name),
    do:
      "This transaction is not the one this page prepared, so it can't be followed here. Check it in your wallet activity."

  defp check(socket, %{step: nil}), do: socket

  defp check(socket, %{hash: hash, reads: reads, review: review, step: step}) do
    start_async(socket, {:onchain_step, hash}, fn ->
      if reads > 0, do: Process.sleep(@recheck_ms)
      Outcome.of(ChainClient, review, step, hash)
    end)
  end

  defp wallets(linked, joiner), do: Enum.map_join(linked, joiner, &short/1)

  defp short(address), do: RegentFormat.short_address(address)
end
