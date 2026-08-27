defmodule TechtreeWeb.MethodSurface do
  @moduledoc """
  What a published address says when it is asked to accept something.

  Almost every address here is a read, and a caller who tried to write to one
  used to be told the address did not exist. That is true of the method and
  false of the address, and the difference matters to anyone checking what this
  site accepts: a `404` invites them to keep hunting for the write endpoint,
  while a `405` says there is not one to find.

  **There is one exception, and this is where a reader learns it.**
  `POST /api/v1/submissions` accepts a finished run somebody publishes. It is
  the only address on this site that accepts anything at all, it accepts one
  method, and everything about what happens to a body sent there is in
  `Techtree.Network.Ingest`. Every other address, and every other method at that
  one, refuses.

  So an address the routing table answers refuses every mutating method it does
  not answer, with `405` and an `Allow` header naming the methods it does. An
  address the table does not know stays a `404` — there is nothing there whose
  methods could be described. Which addresses those are, and which methods
  each answers, is read off the routing table itself rather than listed again
  here, so the plug and the table cannot drift apart.

  The refusal is the shape every other refusal on this site takes: a stable
  code, a message safe to show a stranger, and whether retrying could help.
  """

  @behaviour Plug

  alias TechtreeWeb.ExactResponse

  @mutations ~w(POST PUT PATCH DELETE)

  # A `GET` route answers `HEAD` too; nothing else on this site is implied by
  # anything else.
  @implied %{"GET" => ["GET", "HEAD"], "POST" => ["POST"]}

  @impl Plug
  def init(opts), do: opts

  @impl Plug
  def call(%Plug.Conn{method: method} = conn, _opts) when method in @mutations do
    case answered(conn) do
      [] ->
        conn

      methods ->
        if method in methods do
          conn
        else
          conn
          |> Plug.Conn.put_resp_header("allow", Enum.join(methods, ", "))
          |> ExactResponse.send_error(
            405,
            :method_not_allowed,
            refusal(methods),
            false
          )
          |> Plug.Conn.halt()
        end
    end
  end

  @impl Plug
  def call(conn, _opts), do: conn

  defp answered(conn) do
    Enum.flat_map(@implied, fn {method, implied} ->
      if is_map(
           Phoenix.Router.route_info(TechtreeWeb.Router, method, conn.request_path, conn.host)
         ),
         do: implied,
         else: []
    end)
  end

  defp refusal(methods) do
    if "POST" in methods do
      "this address accepts a published run, and nothing else"
    else
      "this address publishes and does not accept anything"
    end
  end
end
