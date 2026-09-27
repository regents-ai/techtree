defmodule TechtreeWeb.CanonicalHost do
  @moduledoc """
  The site lives at one address. A visit to its www. name is sent to the same
  page there, because a page opened on www. could never connect back to the
  server.
  """

  @behaviour Plug

  import Plug.Conn

  alias TechtreeWeb.Endpoint

  @impl Plug
  def init(opts), do: opts

  @impl Plug
  def call(%Plug.Conn{host: "www." <> host} = conn, _opts) do
    if host == Endpoint.host() do
      conn
      |> put_resp_header("location", Endpoint.url() <> conn.request_path <> query_suffix(conn))
      |> send_resp(:moved_permanently, "")
      |> halt()
    else
      conn
    end
  end

  def call(conn, _opts), do: conn

  defp query_suffix(%Plug.Conn{query_string: ""}), do: ""
  defp query_suffix(%Plug.Conn{query_string: query}), do: "?" <> query
end
