defmodule Techtree.OfflineHttp do
  @moduledoc """
  The HTTP adapter every test runs with (`config :req, :default_options` in
  config/test.exs): a request to this machine goes through as usual, and one to
  any other host raises where it starts, so a quick outside call fails the run
  as surely as a lingering one.
  """

  @local ["127.0.0.1", "localhost", "::1"]

  @spec run(Req.Request.t()) :: {Req.Request.t(), Req.Response.t() | Exception.t()}
  def run(%Req.Request{url: %URI{host: host}} = request) when host in @local,
    do: Req.Finch.run(request)

  def run(%Req.Request{url: url}),
    do: raise("a test tried to reach #{url.scheme}://#{url.host}; tests stay on this machine")
end
