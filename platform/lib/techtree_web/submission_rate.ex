defmodule TechtreeWeb.SubmissionRate do
  @moduledoc """
  How many runs one caller may publish before being asked to wait.

  Every other address on this site is a read and is happy to be read from as
  often as anybody likes. The one address that accepts something is not, so it
  is counted, and a caller over the limit is told to come back — with the
  number of seconds until they may, because a refusal that does not say when is
  a refusal that invites a retry loop.

  This is the only refusal on the site that says retrying could help, and it is
  true here: the window turns over.
  """

  @behaviour Plug

  alias Techtree.Network.RateLimit
  alias TechtreeWeb.ExactResponse

  @impl Plug
  def init(options), do: options

  @impl Plug
  def call(conn, _options) do
    case RateLimit.allow(conn.remote_ip) do
      :ok ->
        conn

      {:error, seconds} ->
        conn
        |> Plug.Conn.put_resp_header("retry-after", Integer.to_string(seconds))
        |> ExactResponse.send_error(
          429,
          :submission_rate_limited,
          "runs are published one at a time by a person, not in a stream; try again shortly",
          true
        )
        |> Plug.Conn.halt()
    end
  end
end
