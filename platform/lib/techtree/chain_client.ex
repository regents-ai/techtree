defmodule Techtree.ChainClient do
  @moduledoc """
  JSON-RPC reads at the latest block of the chain a review names. Every read is at
  `latest`: never count confirmations and never wait for `safe` or `finalized`. The
  node is the site's own for the chain (`:chain_nodes`), never the public address a
  wallet adds the chain with, so a private node or a lab fork reads what the site's
  steps sent. `RegentChain.Outcome` reads sent steps through `transaction/2` and
  `receipt/2`; Regent Credits also reads the newest block number and the logs its
  deposit reader asks for.
  """

  @behaviour RegentCredits.ChainClient
  @behaviour RegentPoints.ChainClient

  @doc "The transaction sent as `hash`, or `nil` while the chain does not know it."
  @impl RegentCredits.ChainClient
  def transaction(chain, hash), do: rpc(chain, "eth_getTransactionByHash", [hash])

  @doc "The receipt for `hash`, or `nil` while it has not landed."
  @impl RegentCredits.ChainClient
  def receipt(chain, hash), do: rpc(chain, "eth_getTransactionReceipt", [hash])

  @doc "The newest block number."
  @impl RegentCredits.ChainClient
  def block_number(chain) do
    with {:ok, "0x" <> hex} <- rpc(chain, "eth_blockNumber", []) do
      {:ok, String.to_integer(hex, 16)}
    end
  end

  @doc "`eth_getLogs` with `filter` as given."
  @impl RegentCredits.ChainClient
  def logs(chain, filter), do: rpc(chain, "eth_getLogs", [filter])

  @doc "The native balance of `address` in wei."
  def balance(chain, address) do
    with {:ok, "0x" <> hex} <- rpc(chain, "eth_getBalance", [address, "latest"]) do
      {:ok, String.to_integer(hex, 16)}
    end
  end

  @doc """
  One JSON-RPC request to the node; one that gets no answer counts in
  `health.chain_request_failures.total` under `scope`, the caller's fixed name.
  `timeouts` are Req's own options, for a caller that must hear back sooner than
  five seconds. `Techtree.ChainHead` passes both.
  """
  @impl RegentPoints.ChainClient
  def rpc(
        %{chain_id: chain_id},
        method,
        params,
        scope \\ "wallet",
        timeouts \\ [receive_timeout: 5_000]
      )
      when is_binary(scope) and is_list(timeouts) do
    url = :techtree |> Application.fetch_env!(:chain_nodes) |> Map.fetch!(chain_id)
    chain = %{chain_id: chain_id, scope: scope}

    case Req.post(
           url,
           [json: %{jsonrpc: "2.0", id: 1, method: method, params: params}, retry: false] ++
             timeouts
         ) do
      {:ok, %{status: 200, body: %{"result" => result}}} -> {:ok, result}
      {:ok, %{body: %{"error" => error}}} -> failed(chain, method, {:rpc, error})
      {:ok, %{status: status}} -> failed(chain, method, {:http, status})
      {:error, error} -> failed(chain, method, error)
    end
  end

  defp failed(chain, method, reason) do
    :telemetry.execute([:techtree, :chain, :failure], %{count: 1}, %{
      method: method,
      class: class(reason),
      chain_id: chain.chain_id,
      scope: chain.scope
    })

    {:error, reason}
  end

  defp class({:rpc, _error}), do: "rpc"
  defp class({:http, status}), do: "http_#{status}"

  defp class(%Req.TransportError{reason: reason}) when reason in [:timeout, :connect_timeout],
    do: "timeout"

  defp class(_transport), do: "transport"
end
