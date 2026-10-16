defmodule TechtreeWeb.Plugs.Parsers do
  @moduledoc """
  `Plug.Parsers`, with a body it rejects reported against the request as it
  stands here. Phoenix otherwise renders that error for the request as it
  entered the endpoint, before `RegentAgentAccess.Plug` chose JSON for `/api`
  paths, so an API caller sending a malformed body got an HTML page.

  A body over its limit, or one that does not decode, is reported against the
  request its last read returned (`TechtreeWeb.Plugs.Parsers.LastRead`).
  """

  @behaviour Plug

  @impl Plug
  def init(opts) do
    {parsers, opts} = Keyword.pop!(opts, :parsers)

    Plug.Parsers.init(
      [parsers: Enum.map(parsers, &{TechtreeWeb.Plugs.Parsers.LastRead, parser: &1})] ++ opts
    )
  end

  @impl Plug
  def call(conn, opts) do
    Plug.Parsers.call(conn, opts)
  rescue
    error -> Plug.Conn.WrapperError.reraise(conn, :error, error, __STACKTRACE__)
  end
end
