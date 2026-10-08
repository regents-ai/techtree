defmodule Techtree.WalletBench.BaseCheck do
  @moduledoc """
  The bench's own check of a wallet the harness reported (the survey's
  `verify-base.py`): from Base (`Techtree.WalletBench.BaseRpc`) at one block, the chain id, whether
  the address holds code, its ETH and USDC balances and its nonce. Given the
  message and signature the harness printed, it also checks who signed: the
  EIP-191 signer is recovered first, which decides it for an account without
  code and for a key-delegated one (EIP-7702); an account with code that the
  key did not sign for, such as a smart wallet, is asked itself at that block
  (ERC-1271 `isValidSignature`). Read-only.

  A check is a map with string keys, the shape it is stored in on the turn, so
  a stored check and a new one read the same way.
  """

  import Techtree.WalletBench.BaseRpc, only: [call: 2, integer: 1]

  alias Techtree.WalletBench.BaseRpc

  @is_valid_signature "0x1626ba7e"

  @type signed :: %{message: String.t(), encoding: String.t(), signature: String.t()}

  @doc "Checks `address` on Base, and the signature when one was printed."
  @spec check(String.t(), signed() | nil) :: {:ok, map()} | {:error, term()}
  def check(address, signed) do
    if address =~ ~r/\A0x[0-9a-fA-F]{40}\z/ do
      chain(address, signed)
    else
      {:ok, %{"address" => address, "problem" => "This is not an EVM address."}}
    end
  end

  @doc "The check as plain lines, for the judge and the page."
  @spec describe(map()) :: String.t()
  def describe(%{"problem" => problem, "address" => address}),
    do: "address #{address}\n#{problem}\n"

  def describe(check) do
    lines = [
      "## Base RPC (#{BaseRpc.url()}) at block #{check["block"]}, #{check["at"]}",
      "address #{check["address"]}",
      "chain_id #{check["chain_id"]}",
      "code #{if check["code_bytes"] == 0, do: "0x", else: "#{check["code_bytes"]} bytes"}",
      "eth_wei #{check["eth_wei"]}",
      "usdc_units #{check["usdc_units"]}",
      "nonce #{check["nonce"]}"
    ]

    signature =
      case check do
        %{"signature" => %{"recovered" => recovered, "matches_address" => matches}} ->
          ["## signature check", "eip191_recovered #{recovered}", "matches_address #{matches}"]

        %{"signature" => %{"method" => "erc1271", "matches_address" => matches}} ->
          [
            "## signature check",
            "erc1271_isValidSignature #{matches}",
            "matches_address #{matches}"
          ]

        %{"signature" => %{"open" => reason}} ->
          ["## signature check", "open: #{reason}"]

        _no_signature ->
          []
      end

    Enum.join(lines ++ signature, "\n") <> "\n"
  end

  defp chain(address, signed) do
    with {:ok, block} <- call("eth_getBlockByNumber", ["latest", false]),
         tag = block["number"],
         {:ok, chain_id} <- call("eth_chainId", []),
         {:ok, code} <- call("eth_getCode", [address, tag]),
         {:ok, wei} <- call("eth_getBalance", [address, tag]),
         {:ok, nonce} <- call("eth_getTransactionCount", [address, tag]),
         {:ok, usdc} <- BaseRpc.usdc_balance(address, tag) do
      check = %{
        "address" => address,
        "block" => integer(tag),
        "at" => block["timestamp"] |> integer() |> DateTime.from_unix!() |> DateTime.to_iso8601(),
        "chain_id" => integer(chain_id),
        "code_bytes" => div(byte_size(code) - 2, 2),
        "eth_wei" => integer(wei),
        "usdc_units" => usdc,
        "nonce" => integer(nonce)
      }

      {:ok, signature(check, signed)}
    end
  end

  defp signature(check, nil), do: check

  defp signature(check, signed) do
    result =
      case message_bytes(signed) do
        {:ok, message} -> signed_by(check, message, signed.signature)
        {:error, reason} -> %{"open" => "the message could not be read (#{reason})"}
      end

    Map.put(
      check,
      "signature",
      Map.merge(result, %{"message" => signed.message, "value" => signed.signature})
    )
  end

  defp signed_by(check, message, signature) do
    by_key = by_key(check, message, signature)

    if check["code_bytes"] > 0 and by_key["matches_address"] != true,
      do: by_contract(check, message, signature),
      else: by_key
  end

  defp by_key(check, message, signature) do
    case Siwa.EvmPersonalSign.recover_personal_address(message, signature) do
      {:ok, recovered} ->
        %{
          "recovered" => recovered,
          "matches_address" => String.downcase(recovered) == String.downcase(check["address"])
        }

      {:error, reason} ->
        %{"open" => "the signature could not be recovered (#{reason})"}
    end
  end

  # isValidSignature(bytes32 hash, bytes signature) answers its own selector when the account accepts the signature.
  defp by_contract(check, message, "0x" <> hex) when rem(byte_size(hex), 2) == 0 do
    hash = Base.encode16(Siwa.EvmPersonalSign.personal_hash(message), case: :lower)
    length = div(byte_size(hex), 2)
    padded = String.pad_trailing(String.downcase(hex), 64 * div(length + 31, 32), "0")
    data = @is_valid_signature <> hash <> word(64) <> word(length) <> padded

    case call("eth_call", [%{to: check["address"], data: data}, BaseRpc.hex(check["block"])]) do
      {:ok, @is_valid_signature <> _padding} ->
        %{"method" => "erc1271", "matches_address" => true}

      {:ok, _other} ->
        %{"method" => "erc1271", "matches_address" => false}

      {:error, _error} ->
        %{"open" => "the account holds code, and it did not answer a signature check"}
    end
  end

  defp by_contract(_check, _message, _signature),
    do: %{"open" => "the account holds code, and the signature is not hex"}

  defp word(integer), do: String.pad_leading(Integer.to_string(integer, 16), 64, "0")

  defp message_bytes(%{encoding: "text", message: message}), do: {:ok, message}

  defp message_bytes(%{encoding: "hex", message: "0x" <> hex}) do
    case Base.decode16(hex, case: :mixed) do
      {:ok, bytes} -> {:ok, bytes}
      :error -> {:error, :invalid_message_hex}
    end
  end

  defp message_bytes(_signed), do: {:error, :invalid_message_hex}
end
