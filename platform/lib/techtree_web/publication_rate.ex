defmodule TechtreeWeb.PublicationRate do
  @moduledoc """
  How many runs one caller may publish before being asked to wait.

  Every other address on this site is a read, with a generous budget per
  caller (`TechtreeWeb.Endpoint`). The one address that accepts something has
  a small budget of its own, so a caller over the limit is told to come back — with the number of seconds until
  they may, because a refusal that does not say when is a refusal that invites
  a retry loop.

  The refusal says retrying could help, and it is true here: the window turns
  over.

  Every answer to that address says where the caller stands in this budget,
  named `publication`, with the same `RateLimit-Policy` and `RateLimit` headers
  the rest of the API sends for its own budget. The rest of the API's budget
  does not count this address: this one is the limit here.

  It stands in the endpoint, in front of the parser, so a caller already over
  the limit is refused before their body is read, let alone decoded. Each
  request is counted here and nowhere else. `TechtreeWeb.PublicationAddress`
  decides which requests those are, and `TechtreeWeb.ClientAddress` says who
  the caller is.

  The refusal also closes the connection. A body that was sent is otherwise
  still read off a kept-alive connection after the answer, and the point of
  refusing here is that it is not read.
  """

  @behaviour Plug

  alias Techtree.Network
  alias Techtree.RateLimit
  alias TechtreeWeb.ClientAddress
  alias TechtreeWeb.ExactResponse
  alias TechtreeWeb.PublicationAddress

  @impl Plug
  def init(options), do: options

  @impl Plug
  def call(conn, _options) do
    if PublicationAddress.post?(conn), do: count(conn), else: conn
  end

  defp count(conn) do
    {key, _source} = ClientAddress.key(conn)
    limits = Network.rate_limit()

    case RateLimit.admit(
           {:publication, key},
           Keyword.fetch!(limits, :limit),
           Keyword.fetch!(limits, :window_seconds)
         ) do
      {:ok, budget} ->
        RegentAgentAccess.RateLimit.put_headers(conn, "publication", budget)

      {:error, :rate_limited, budget} ->
        conn
        |> RegentAgentAccess.RateLimit.put_headers("publication", budget)
        |> ExactResponse.put_api_headers()
        |> Plug.Conn.put_resp_header("retry-after", Integer.to_string(budget.reset))
        |> Plug.Conn.put_resp_header("connection", "close")
        |> ExactResponse.send_error(
          429,
          :publication_rate_limited,
          "runs are published and withdrawn one at a time by a person, not in a stream; try again shortly",
          "Wait the seconds in the Retry-After header, then send the same request again."
        )
        |> Plug.Conn.halt()
    end
  end
end
