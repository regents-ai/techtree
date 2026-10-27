defmodule TechtreeWeb.CreditsPressTest do
  # Invariant: a press that asks the server for its steps (prepare_and_send) is
  # never handed a Buy the fresh build finds certain to fail, from the shown
  # wallet's figures at the latest block; the button shows why instead. A Buy
  # that may go through, and an approval, are handed over. Keyfleet, 27 Oct: the
  # reply skipped this check and a wallet holding nothing was asked to send.
  use ExUnit.Case, async: true
  use ExUnitProperties

  alias TechtreeWeb.{CreditsPanel, OnchainSteps}
  alias Phoenix.Component

  @wallet "0x" <> String.duplicate("a", 40)

  property "a Buy certain to fail is never handed to the wallet" do
    check all(
            dollars <- integer(5..500),
            usdc <- integer(0..600_000_000),
            allowance <- integer(0..600_000_000)
          ) do
      micro = dollars * 1_000_000
      socket = panel(%{usdc: usdc, allowance: allowance})
      press = %{"form" => %{"amount" => Integer.to_string(dollars)}}

      {:reply, buy, _socket} =
        CreditsPanel.handle_event("prepare_and_send", Map.put(press, "step", "buy"), socket)

      {:reply, approve, _socket} =
        CreditsPanel.handle_event("prepare_and_send", Map.put(press, "step", "approve"), socket)

      if usdc < micro or allowance < micro,
        do: assert(buy == %{}),
        else: assert(%{review: %{}, send: "buy"} = buy)

      assert %{review: %{}, send: "approve"} = approve
    end
  end

  # The panel signed in with its one wallet active, after that wallet's figures
  # were read at the latest block.
  defp panel(latest) do
    %Phoenix.LiveView.Socket{}
    |> OnchainSteps.init()
    |> Component.assign(
      id: "credits",
      linked: [@wallet],
      own: @wallet,
      active: @wallet,
      signer: @wallet,
      wallet: @wallet,
      amount: "5",
      number: Ecto.UUID.generate(),
      numbers: %{},
      usdc: latest.usdc,
      allowance: latest.allowance,
      latest: latest,
      purchases: %{}
    )
  end
end
