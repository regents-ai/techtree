defmodule Techtree.Jobs.StakingTest do
  # A `USDCRevenueDeposited` log, shaped as a Base node returns it, read as a
  # job payment: its fields, a deposit with another tag left out, and anything
  # that is not a direct deposit from staking with the reference refused.
  use ExUnit.Case, async: true

  alias Techtree.Jobs.Staking

  @reference "0x9f2c41d07b5e8a63c1f0d2e4b6a8c0e2f4a6b8d0c2e4f6a8b0d2c4e6f8a0b2c4"

  # cast keccak "USDCRevenueDeposited(uint256,uint256,uint256,uint8,address,bytes32,bytes32)"
  @topic0 "0x1a150e3db61cdcdf841d24acf00159c2e184f84c02c7ec5ab3507766dae59e51"

  # cast abi-encode "f(uint256,uint256,uint256,bytes32)" 1234567 400000 834567 <techtree.job>
  @data "0x000000000000000000000000000000000000000000000000000000000012d6870000000000000000000000000000000000000000000000000000000000061a8000000000000000000000000000000000000000000000000000000000000cbc0774656368747265652e6a6f620000000000000000000000000000000000000000"

  @log %{
    "address" => "0xb027Dc261636E30cBc0FE25B2F8E1eD273354aB5",
    "topics" => [
      @topic0,
      "0x0000000000000000000000000000000000000000000000000000000000000000",
      "0x000000000000000000000000d8da6bf26964af9d7eed9e03e53415d37aa96045",
      @reference
    ],
    "data" => @data,
    "blockNumber" => "0x2381a3e",
    "blockHash" => "0x5d1c4bb1f3b0b7e3cbd9a7b1b5e0a4f6c2d8e9f0a1b2c3d4e5f60718293a4b5c",
    "transactionHash" => "0x8e3f0c1a2b4d6e8f0a1c3e5d7b9f1a3c5e7d9b1f3a5c7e9d1b3f5a7c9e1d3b5f",
    "transactionIndex" => "0x7",
    "logIndex" => "0x1f",
    "removed" => false
  }

  test "a job payment's fields are read from its log" do
    assert Staking.decode(@log, @reference) ==
             {:ok,
              %{
                transaction_hash:
                  "0x8e3f0c1a2b4d6e8f0a1c3e5d7b9f1a3c5e7d9b1f3a5c7e9d1b3f5a7c9e1d3b5f",
                log_index: 31,
                depositor: "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
                amount: 1_234_567,
                block_number: 37_231_166
              }}
  end

  test "a deposit with another tag is not a job payment" do
    credits = Base.encode16(String.pad_trailing("regent.credits", 32, <<0>>), case: :lower)
    log = Map.update!(@log, "data", &(String.slice(&1, 0, 2 + 192) <> credits))

    assert Staking.decode(log, @reference) == {:ok, nil}
  end

  test "anything but a direct deposit from staking with the reference is refused" do
    other = "0x" <> String.duplicate("ab", 32)

    for log <- [
          Map.put(@log, "address", "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"),
          Map.update!(@log, "topics", &List.replace_at(&1, 0, other)),
          Map.update!(
            @log,
            "topics",
            &List.replace_at(&1, 1, "0x" <> String.pad_leading("1", 64, "0"))
          ),
          Map.update!(@log, "topics", &List.replace_at(&1, 3, other)),
          Map.update!(@log, "topics", &Enum.take(&1, 3)),
          Map.update!(@log, "data", &String.slice(&1, 0, 130)),
          Map.put(@log, "data", @data <> "00"),
          Map.put(@log, "transactionHash", "0x1234"),
          Map.delete(@log, "logIndex")
        ] do
      assert Staking.decode(log, @reference) == :error
    end
  end
end
