defmodule TechtreeWeb.Parsers do
  @moduledoc """
  `Plug.Parsers`, with a body it refuses reported against the request as it
  stands here. Phoenix otherwise renders that error for the request as it
  entered the endpoint, before `RegentAgentAccess.Plug` chose JSON for `/api`
  paths, so an API caller sending a malformed body got an HTML page.
  """

  @behaviour Plug

  @impl Plug
  def init(opts), do: Plug.Parsers.init(opts)

  @impl Plug
  def call(conn, opts) do
    Plug.Parsers.call(conn, opts)
  rescue
    error -> Plug.Conn.WrapperError.reraise(conn, :error, error, __STACKTRACE__)
  end
end
