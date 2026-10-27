defmodule TechtreeWeb.Plugs.NoTrailingSlash do
  @moduledoc """
  Every page and API call has one address. The router also matches each route
  with a slash at the end, which would give every page a second address, so any
  address ending in a slash other than the homepage gets the answer an address
  that names nothing gets, in the format `RegentAgentAccess.Plug` chose for it.
  """

  @behaviour Plug

  @impl Plug
  def init(opts), do: opts

  @impl Plug
  def call(%Plug.Conn{request_path: "/"} = conn, _opts), do: conn

  def call(%Plug.Conn{request_path: path} = conn, _opts) do
    if String.ends_with?(path, "/"),
      do: raise(Phoenix.Router.NoRouteError, conn: conn, router: TechtreeWeb.Router),
      else: conn
  end
end
