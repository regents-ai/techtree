defmodule Techtree.Jobs.PaymentTest do
  # What pays a job order, with no chain read:
  # - the two calls, byte for byte as Foundry's `cast calldata` encodes them;
  # - the tag and a fresh reference;
  # - over random deposits, heads and stretches: a deposit counts only once it
  #   is deep enough, and an order is paid exactly when what counts reaches the
  #   quote; expiry never beats a payment.
  use ExUnit.Case, async: true
  use ExUnitProperties

  alias RegentChain.BuilderCode
  alias Techtree.Jobs.Payment

  @reference "0x9f2c41d07b5e8a63c1f0d2e4b6a8c0e2f4a6b8d0c2e4f6a8b0d2c4e6f8a0b2c4"
  @staking "0xb027dc261636e30cbc0fe25b2f8e1ed273354ab5"
  @usdc "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"

  # cast --format-bytes32-string techtree.job
  @tag_bytes32 "0x74656368747265652e6a6f620000000000000000000000000000000000000000"

  # cast calldata "approve(address,uint256)" 0xb027Dc261636E30cBc0FE25B2F8E1eD273354aB5 1234567
  @approve "0x095ea7b3000000000000000000000000b027dc261636e30cbc0fe25b2f8e1ed273354ab5000000000000000000000000000000000000000000000000000000000012d687"

  # cast calldata "depositUSDC(uint256,bytes32,bytes32)" 1234567 <tag> <reference>
  @deposit "0x7dc6bb98000000000000000000000000000000000000000000000000000000000012d68774656368747265652e6a6f6200000000000000000000000000000000000000009f2c41d07b5e8a63c1f0d2e4b6a8c0e2f4a6b8d0c2e4f6a8b0d2c4e6f8a0b2c4"

  @confirmations 300

  test "the tag is techtree.job padded to 32 bytes" do
    assert Payment.tag() == @tag_bytes32
  end

  test "a reference is 32 fresh random bytes" do
    references = for _ <- 1..50, do: Payment.reference()

    assert Enum.all?(references, &(&1 =~ ~r/\A0x[0-9a-f]{64}\z/))
    assert references |> Enum.uniq() |> length() == 50
  end

  test "a quoted order is paid by an approval of the quote, then the deposit" do
    order = %{state: :quoted, quote_amount: 1_234_567, payment_reference: @reference}

    assert {:ok, [approve, deposit]} = Payment.calls(order)

    assert %{step: "approve", to: @usdc, value: "0x0", chain_id: 8453} = approve
    assert BuilderCode.call(approve.data) == @approve

    assert %{step: "deposit", to: @staking, value: "0x0", chain_id: 8453} = deposit
    assert BuilderCode.call(deposit.data) == @deposit
  end

  test "an order that is not quoted has nothing to pay" do
    for state <- [:requested, :checking, :paid, :expired, :refused, :cancelled] do
      order = %{state: state, quote_amount: 1_000, payment_reference: @reference}
      assert {:error, :not_quoted} = Payment.calls(order)
    end
  end

  property "an order is paid exactly when deposits deep enough reach the quote" do
    check all(
            quote <- integer(1..5_000),
            deposits <- list_of({integer(0..400), integer(1..2_000)}, max_length: 8),
            blocks <- integer(1..60),
            steps <- list_of(integer(0..25), min_length: 1, max_length: 60)
          ) do
      start = 1_000
      deposits = Enum.map(deposits, fn {offset, amount} -> {start + offset, amount} end)
      reader = %{next: start, head: start, recorded: [], state: :quoted}

      reader =
        Enum.reduce(steps, reader, fn step, reader ->
          read(%{reader | head: reader.head + step}, deposits, quote, blocks)
        end)

      # Reading on at the last head catches up with every block deep enough.
      reader =
        Enum.reduce(1..(div(1_400, blocks) + 1), reader, fn _, r ->
          read(r, deposits, quote, blocks)
        end)

      deep_enough =
        for {block, amount} <- deposits, block <= reader.head - @confirmations + 1, do: amount

      assert Enum.sort(reader.recorded) == Enum.sort(deep_enough)
      assert reader.state == if(Enum.sum(deep_enough) >= quote, do: :paid, else: :quoted)
    end
  end

  property "paying wins over the quote running out" do
    check all(
            quote <- integer(1..10_000),
            received <- integer(0..20_000),
            expiry_passed? <- boolean()
          ) do
      expected =
        cond do
          received >= quote -> :paid
          expiry_passed? -> :expired
          true -> :quoted
        end

      assert Payment.outcome(quote, Decimal.new(received), expiry_passed?) == expected
    end
  end

  # One payment read, as `Techtree.Jobs.Order.ReadPayment` makes it.
  defp read(reader, deposits, quote, blocks) do
    %{from: from, to: to, frontier: frontier} =
      Payment.stretch(reader.next, reader.head, @confirmations, blocks)

    assert to <= frontier

    read = for {block, amount} <- deposits, block >= from and block <= to, do: amount
    recorded = read ++ reader.recorded

    state =
      case reader.state do
        :quoted -> Payment.outcome(quote, Enum.sum(recorded), false)
        paid -> paid
      end

    %{reader | next: max(reader.next, to + 1), recorded: recorded, state: state}
  end
end
