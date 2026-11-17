defmodule Techtree.Jobs.PaymentTest do
  # What pays a job order, with no chain read:
  # - the two calls, byte for byte as Foundry's `cast calldata` encodes them;
  # - the tag and a fresh reference;
  # - over random amounts: an order is paid exactly when what was received
  #   reaches the quote, and expiry never beats a payment. The reader's own
  #   property, over random deposits and heads, is in `reader_test.exs`.
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
end
