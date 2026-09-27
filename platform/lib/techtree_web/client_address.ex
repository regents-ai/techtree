defmodule TechtreeWeb.ClientAddress do
  @moduledoc """
  Who sent a request, as far as a per-caller limit can tell.

  In production nobody connects to this application directly. Fly's proxy
  terminates every public connection and opens its own to the machine, so the
  connection's peer is the proxy and is the same for every visitor. Measured on
  the running machine on 27 September 2026, public requests arrived from
  `172.16.6.2` — seen here as `::ffff:172.16.6.2`, because the release listens
  on `::` and an IPv4 peer arrives in its IPv4-mapped form. The machine's own
  network and gateway are a different range, `172.19.6.0/29`. A limit keyed on
  the peer would be one budget shared by everybody.

  ## The trust boundary

  Fly's proxy writes `fly-client-ip` itself, replacing whatever a client sent
  under that name, so the header is believed only on a connection that comes
  from the proxy's range, `172.16.0.0/16`. Nothing outside Fly's host can open a
  connection to the machine from that range: the public reaches it only through
  the proxy, and other machines in the organization reach it over the private
  IPv6 network. A request from the proxy without exactly one address in that
  header is not one Fly sends, and is not answered.

  From any other peer — a direct connection, local development, a test — the
  peer is the caller and no header is read.

  `x-forwarded-for` is never read. Fly appends to it rather than replacing it,
  so everything left of the entries Fly added is whatever the client wrote.

  An IPv6 client is keyed by its /64, the block one host is ordinarily handed,
  so that one host cannot spend the budget once for every address it holds.

  This is the local form of the template's trusted-proxy adapter; when that is
  published it replaces this module.
  """

  import Plug.Conn, only: [get_req_header: 2]

  @doc """
  The key a per-caller limit counts this request under.
  """
  @spec key(Plug.Conn.t()) :: :inet.ip_address()
  def key(%Plug.Conn{remote_ip: {0, 0, 0, 0, 0, 0xFFFF, 0xAC10, _host}} = conn) do
    [value] = get_req_header(conn, "fly-client-ip")
    {:ok, address} = value |> String.to_charlist() |> :inet.parse_strict_address()
    block(address)
  end

  def key(%Plug.Conn{remote_ip: peer}), do: peer

  defp block({_, _, _, _} = ipv4), do: ipv4
  defp block({a, b, c, d, _, _, _, _}), do: {a, b, c, d, 0, 0, 0, 0}
end
