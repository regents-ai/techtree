defmodule Techtree.WalletBench.BaseCheck do
  @moduledoc """
  The bench's own check of a wallet the harness reported (the survey's
  `verify-base.py`): from Base (`Techtree.WalletBench.BaseRpc`) at one block, the chain id, whether
  the address holds code, its ETH and USDC balances and its nonce. Given the
  message and signature the harness printed, it also recovers the EIP-191
  signer for an account without code; for an account with code the check is
  left open. Read-only.

  A check is a map with string keys, the shape it is stored in on the turn, so
  a stored check and a new one read the same way.
  """

  import Techtree.WalletBench.BaseRpc, only: [call: 2, integer: 1]

  alias Techtree.WalletBench.BaseRpc

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

  defp signature(%{"code_bytes" => 0} = check, signed) do
    result =
      with {:ok, message} <- message_bytes(signed),
           {:ok, recovered} <-
             Siwa.EvmPersonalSign.recover_personal_address(message, signed.signature) do
        %{
          "recovered" => recovered,
          "matches_address" => String.downcase(recovered) == String.downcase(check["address"])
        }
      else
        {:error, reason} -> %{"open" => "the signature could not be recovered (#{reason})"}
      end

    Map.put(
      check,
      "signature",
      Map.merge(result, %{"message" => signed.message, "value" => signed.signature})
    )
  end

  defp signature(check, signed) do
    Map.put(check, "signature", %{
      "open" => "the account holds code, so an EIP-191 recovery does not decide it",
      "message" => signed.message,
      "value" => signed.signature
    })
  end

  defp message_bytes(%{encoding: "text", message: message}), do: {:ok, message}

  defp message_bytes(%{encoding: "hex", message: "0x" <> hex}) do
    case Base.decode16(hex, case: :mixed) do
      {:ok, bytes} -> {:ok, bytes}
      :error -> {:error, :invalid_message_hex}
    end
  end

  defp message_bytes(_signed), do: {:error, :invalid_message_hex}
end
