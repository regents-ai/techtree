defmodule Techtree.BaseFork do
  @moduledoc """
  A local fork of Base for the `:base_fork` tests: anvil, on a free port,
  forking Base's public node, with the site's Base node pointed at it until the
  tests end, when anvil is stopped.

  Wallets are funded and sent from on the fork only, by anvil's impersonation:
  no key is used and nothing reaches Base itself.
  """

  import ExUnit.Callbacks, only: [on_exit: 1]

  alias Techtree.JobsFixture
  alias Techtree.Jobs.Payment

  @fork_url "https://mainnet.base.org"

  @doc "Starts anvil forking Base and points the site's Base node at it."
  def start! do
    anvil = System.find_executable("anvil") || raise "anvil is not on the PATH"
    {:ok, socket} = :gen_tcp.listen(0, ip: {127, 0, 0, 1})
    {:ok, port} = :inet.port(socket)
    :ok = :gen_tcp.close(socket)

    process =
      Port.open({:spawn_executable, anvil}, [
        :binary,
        :exit_status,
        :stderr_to_stdout,
        args: ["--fork-url", @fork_url, "--host", "127.0.0.1", "--port", to_string(port)]
      ])

    {:os_pid, os_pid} = Port.info(process, :os_pid)
    on_exit(fn -> System.cmd("kill", [to_string(os_pid)]) end)

    url = "http://127.0.0.1:#{port}"
    JobsFixture.put_env(:techtree, :chain_nodes, %{8453 => url})
    await(url, 120)
    # One block of the fork's own, so every quote reads only blocks the fork
    # made, never the forked one from Base's node.
    mine(url, 1)
    url
  end

  @doc "Gives `wallet` gas money and `usdc` of USDC on the fork, and lets it send unsigned."
  def fund(url, wallet, usdc) do
    rpc!(url, "anvil_setBalance", [wallet, "0xde0b6b3a7640000"])
    rpc!(url, "anvil_dealERC20", [wallet, Payment.config()[:usdc], quantity(usdc)])
    rpc!(url, "anvil_impersonateAccount", [wallet])
  end

  @doc "Sends each call from `wallet` on the fork, in order, and requires each to succeed."
  def send!(url, wallet, calls) do
    for call <- calls do
      # A gas limit as a wallet would set it: anvil's own estimate for the
      # deposit sometimes falls short on a fork, and the deposit runs out.
      hash =
        rpc!(url, "eth_sendTransaction", [
          %{from: wallet, to: call.to, data: call.data, value: call.value, gas: "0x7a120"}
        ])

      %{"status" => "0x1"} = receipt(url, hash, 100)
      hash
    end
  end

  # anvil answers a send before it has mined it.
  defp receipt(_url, hash, 0), do: raise("#{hash} was not mined")

  defp receipt(url, hash, tries) do
    case rpc!(url, "eth_getTransactionReceipt", [hash]) do
      nil ->
        Process.sleep(100)
        receipt(url, hash, tries - 1)

      receipt ->
        receipt
    end
  end

  @doc "Mines `count` empty blocks on the fork."
  def mine(url, count), do: rpc!(url, "anvil_mine", [quantity(count)])

  @doc "One JSON-RPC request to the fork."
  def rpc!(url, method, params) do
    %{status: 200, body: %{"result" => result}} =
      Req.post!(url,
        json: %{jsonrpc: "2.0", id: 1, method: method, params: params},
        retry: false,
        receive_timeout: 60_000
      )

    result
  end

  defp await(_url, 0), do: raise("anvil did not start forking #{@fork_url}")

  defp await(url, tries) do
    Req.post!(url,
      json: %{jsonrpc: "2.0", id: 1, method: "eth_blockNumber", params: []},
      retry: false
    )
  rescue
    _not_yet ->
      Process.sleep(500)
      await(url, tries - 1)
  end

  defp quantity(number), do: "0x" <> String.downcase(Integer.to_string(number, 16))
end
