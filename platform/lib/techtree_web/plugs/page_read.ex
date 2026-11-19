defmodule TechtreeWeb.Plugs.PageRead do
  @moduledoc """
  How fast one client address may read the public pages, and the public reads
  beside them that the database answers and the endpoint's request budget does
  not count: the `page_read` allowance in `config :techtree, :limits`, spent
  through `Techtree.Limits`.

  It stands first in the router's `:page_read` pipeline, before the session's
  authority, a page's Markdown or the page itself reads the database, so an
  address over the allowance costs no query. A LiveView page counts its first
  render here; what it does over its socket afterwards, wallet presses and
  navigation between live pages included, never passes the router and is not
  counted. The health check, static files, the socket, the API and the hosted
  MCP server are not counted here: `TechtreeWeb.Endpoint` counts the health
  check and the API under their own budget.

  Over the allowance the answer is 429 with Retry-After, the seconds left of
  the window. Each refusal is counted as `[:techtree, :page_read, :rate_limited]`,
  tagged with where the address came from (`TechtreeWeb.ClientAddress`).
  """

  @behaviour Plug

  import Plug.Conn

  alias Techtree.Limits
  alias TechtreeWeb.ClientAddress

  @impl Plug
  def init(opts), do: opts

  @impl Plug
  def call(conn, _opts) do
    {key, source} = ClientAddress.key(conn)

    case Limits.spend_until(:page_read, key) do
      :ok -> conn
      {:limited, seconds} -> refuse(conn, source, seconds)
    end
  end

  defp refuse(conn, source, seconds) do
    :telemetry.execute([:techtree, :page_read, :rate_limited], %{count: 1}, %{source: source})

    conn
    |> put_resp_header("retry-after", Integer.to_string(seconds))
    |> put_resp_header("cache-control", "no-store")
    |> put_resp_content_type("text/plain")
    |> send_resp(429, "Too many requests. Please wait a moment and try again.\n")
    |> halt()
  end
end
