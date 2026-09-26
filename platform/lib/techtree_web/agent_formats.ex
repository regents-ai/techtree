defmodule TechtreeWeb.AgentFormats do
  @moduledoc """
  Two decisions about how a response is shaped, made before the router so
  that a request no route matches is still answered in kind.

  A request under `/api/` is answered as JSON whatever it asked for, so an
  unknown API address gets the shared JSON error rather than a page. Every
  other response names `Accept` in `Vary`, because the same address can answer
  as HTML or as Markdown depending on what the caller asked for.
  """

  @behaviour Plug

  import Plug.Conn

  @impl Plug
  def init(opts), do: opts

  @impl Plug
  def call(%Plug.Conn{path_info: ["api" | _rest]} = conn, _opts),
    do: put_private(conn, :phoenix_format, "json")

  def call(conn, _opts), do: put_resp_header(conn, "vary", "accept")
end
