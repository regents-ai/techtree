defmodule TechtreeWeb.MethodSurface do
  @moduledoc """
  What a published address says when it is asked to accept something.

  Every address here is a read, and a caller who tried to write to one used to
  be told the address did not exist. That is true of the method and false of
  the address, and the difference matters to anyone checking what this site
  accepts: a `404` invites them to keep hunting for the write endpoint, while a
  `405` says there is not one to find.

  So an address the routing table would answer for `GET` refuses the four
  mutating methods with `405` and an `Allow` header naming the two it does
  answer. An address the table does not know stays a `404` — there is nothing
  there whose methods could be described. Which addresses those are is read off
  the routing table itself rather than listed again here, so the two cannot
  drift apart.

  The refusal is the shape every other refusal on this site takes: a stable
  code, a message safe to show a stranger, and whether retrying could help.
  """

  @behaviour Plug

  alias TechtreeWeb.ExactResponse

  @mutations ~w(POST PUT PATCH DELETE)
  @allowed "GET, HEAD"

  @impl Plug
  def init(opts), do: opts

  @impl Plug
  def call(%Plug.Conn{method: method} = conn, _opts) when method in @mutations do
    if published?(conn) do
      conn
      |> Plug.Conn.put_resp_header("allow", @allowed)
      |> ExactResponse.send_error(
        405,
        :method_not_allowed,
        "this address publishes and does not accept anything",
        false
      )
      |> Plug.Conn.halt()
    else
      conn
    end
  end

  @impl Plug
  def call(conn, _opts), do: conn

  defp published?(conn) do
    is_map(Phoenix.Router.route_info(TechtreeWeb.Router, "GET", conn.request_path, conn.host))
  end
end
