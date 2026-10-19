defmodule Techtree.EvidenceShelf do
  @moduledoc """
  The evidence store for the browser test server (assets/test/browser): files
  put and read back by key in a folder on this machine, for its partition,
  instead of the private bucket. `config/test.exs` points
  `Techtree.WalletBench.Evidence` here when `TECHTREE_BROWSER_TEST=1`.
  """
  @behaviour Plug

  import Plug.Conn

  @impl Plug
  def init(options), do: options

  @impl Plug
  def call(%{method: "PUT"} = conn, _options) do
    {:ok, body, conn} = read_body(conn, length: 50_000_000)
    path = path(conn)
    File.mkdir_p!(Path.dirname(path))
    File.write!(path, body)
    send_resp(conn, 200, "")
  end

  def call(%{method: "GET"} = conn, _options) do
    case File.read(path(conn)) do
      {:ok, body} -> send_resp(conn, 200, body)
      {:error, :enoent} -> send_resp(conn, 404, "")
    end
  end

  # The request's path is the bucket and the key, each segment encoded.
  defp path(conn) do
    folder =
      Path.join(System.tmp_dir!(), "techtree-evidence-#{System.fetch_env!("MIX_TEST_PARTITION")}")

    Path.join([folder | Enum.map(conn.path_info, &URI.decode/1)])
  end
end
