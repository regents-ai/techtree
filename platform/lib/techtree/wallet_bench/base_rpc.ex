defmodule Techtree.WalletBench.BaseRpc do
  @moduledoc """
  The bench's calls to Base, through the address set as `base_rpc` in
  `:techtree, Techtree.WalletBench`: Base's public RPC, or a local copy of Base
  when testing. One call, one answer; nothing here retries.
  """

  @usdc "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
  @balance_of "0x70a08231"
  @transfer_topic "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

  @doc "Native USDC on Base."
  @spec usdc() :: String.t()
  def usdc, do: @usdc

  @doc "Where the bench reads Base."
  @spec url() :: String.t()
  def url, do: Application.fetch_env!(:techtree, Techtree.WalletBench)[:base_rpc]

  @spec call(String.t(), list()) :: {:ok, term()} | {:error, term()}
  def call(method, params) do
    case request(method, params) do
      {:ok, %Req.Response{status: 200, body: %{"result" => result}}} ->
        {:ok, result}

      {:ok, %Req.Response{status: status, body: body}} ->
        {:error, "Base RPC #{method} answered #{status}: #{inspect(body)}"}

      {:error, exception} ->
        {:error, exception}
    end
  end

  @doc """
  The gas `transaction` needs at the latest block, or `{:refused, reason}` when
  Base answers that it would revert (JSON-RPC error code 3), such as a recipient
  whose code rejects it. Any other error, such as a rate limit, is an error.
  """
  @spec estimate_gas(map()) :: {:ok, pos_integer()} | {:refused, String.t()} | {:error, term()}
  def estimate_gas(transaction) do
    case request("eth_estimateGas", [transaction, "latest"]) do
      {:ok, %Req.Response{status: 200, body: %{"result" => gas}}} ->
        {:ok, integer(gas)}

      {:ok, %Req.Response{status: 200, body: %{"error" => %{"code" => 3, "message" => reason}}}} ->
        {:refused, reason}

      {:ok, %Req.Response{status: status, body: body}} ->
        {:error, "Base RPC eth_estimateGas answered #{status}: #{inspect(body)}"}

      {:error, exception} ->
        {:error, exception}
    end
  end

  defp request(method, params) do
    Req.post(url(),
      json: %{jsonrpc: "2.0", id: 1, method: method, params: params},
      retry: false,
      receive_timeout: 30_000
    )
  end

  @doc "An address's USDC balance at a block tag, in units of 0.000001 USDC."
  @spec usdc_balance(String.t(), String.t()) :: {:ok, non_neg_integer()} | {:error, term()}
  def usdc_balance(address, tag) do
    with {:ok, units} <- call("eth_call", [%{to: @usdc, data: balance_call(address)}, tag]) do
      {:ok, integer(units)}
    end
  end

  @doc "The call data of a USDC transfer of `units` to `to`."
  @spec usdc_transfer(String.t(), non_neg_integer()) :: String.t()
  def usdc_transfer(to, units),
    do: "0xa9059cbb" <> word(to) <> String.pad_leading(Integer.to_string(units, 16), 64, "0")

  @doc """
  Every USDC transfer from or to `address` from `from_block` to `to_block`:
  block, transaction hash, log index, sender, recipient and units, oldest first.
  """
  @spec usdc_transfers(String.t(), non_neg_integer(), non_neg_integer()) ::
          {:ok, [map()]} | {:error, term()}
  def usdc_transfers(address, from_block, to_block) do
    range = %{fromBlock: hex(from_block), toBlock: hex(to_block), address: @usdc}
    topic = "0x" <> word(address)

    with {:ok, out} <- call("eth_getLogs", [Map.put(range, :topics, [@transfer_topic, topic])]),
         {:ok, incoming} <-
           call("eth_getLogs", [Map.put(range, :topics, [@transfer_topic, nil, topic])]) do
      {:ok,
       (out ++ incoming)
       |> Enum.uniq_by(&{&1["transactionHash"], &1["logIndex"]})
       |> Enum.map(&transfer/1)
       |> Enum.sort_by(&{&1["block"], &1["log_index"]})}
    end
  end

  @spec integer(String.t()) :: non_neg_integer()
  def integer("0x" <> hex), do: String.to_integer(hex, 16)

  @spec hex(non_neg_integer()) :: String.t()
  def hex(integer), do: "0x" <> String.downcase(Integer.to_string(integer, 16))

  @doc "A token amount in whole tokens, such as `0.25` for 250000 USDC units."
  @spec decimal(non_neg_integer(), non_neg_integer()) :: String.t()
  def decimal(amount, decimals) do
    amount
    |> Decimal.new()
    |> Decimal.div(Integer.pow(10, decimals))
    |> Decimal.normalize()
    |> Decimal.to_string(:normal)
  end

  defp transfer(log) do
    [_topic, from, to] = log["topics"]

    %{
      "block" => integer(log["blockNumber"]),
      "tx_hash" => log["transactionHash"],
      "log_index" => integer(log["logIndex"]),
      "from" => address(from),
      "to" => address(to),
      "units" => integer(log["data"])
    }
  end

  defp address("0x" <> topic), do: "0x" <> String.slice(topic, 24, 40)

  defp balance_call(address), do: @balance_of <> word(address)

  defp word("0x" <> hex), do: String.pad_leading(String.downcase(hex), 64, "0")
end
