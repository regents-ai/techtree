defmodule TechtreeWeb.PublicationRate do
  @moduledoc """
  How many runs one caller may publish before being asked to wait.

  Every other address on this site is a read and is happy to be read from as
  often as anybody likes. The one address that accepts something is not, so a
  caller over the limit is told to come back — with the number of seconds until
  they may, because a refusal that does not say when is a refusal that invites
  a retry loop.

  This is the only refusal on the site that says retrying could help, and it is
  true here: the window turns over.

  It stands in the endpoint, in front of the parser, so a caller already over
  the limit is refused before their body is read, let alone decoded. Each
  request is counted here and nowhere else. It matches the publication address
  the way the routing table does, by its segments, so a trailing slash is the
  same address and counted the same. `TechtreeWeb.ClientAddress` says who the
  caller is.
  """

  @behaviour Plug

  alias Techtree.Network.RateLimit
  alias TechtreeWeb.ClientAddress
  alias TechtreeWeb.ExactResponse

  @impl Plug
  def init(options), do: options

  @impl Plug
  def call(%Plug.Conn{method: "POST", path_info: ["api", "v1", "publications"]} = conn, _options) do
    case RateLimit.allow(ClientAddress.key(conn)) do
      :ok ->
        conn

      {:error, seconds} ->
        conn
        |> ExactResponse.put_api_headers()
        |> Plug.Conn.put_resp_header("retry-after", Integer.to_string(seconds))
        |> ExactResponse.send_error(
          429,
          :publication_rate_limited,
          "runs are published and withdrawn one at a time by a person, not in a stream; try again shortly",
          true
        )
        |> Plug.Conn.halt()
    end
  end

  def call(conn, _options), do: conn
end
