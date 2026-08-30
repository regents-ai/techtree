defmodule TechtreeWeb.SourceRevision do
  @moduledoc """
  Adds the deployed source revision to every HTTP response.
  """

  import Plug.Conn

  alias Techtree.BuildInfo

  def init(options), do: options

  def call(conn, _options) do
    put_resp_header(conn, "x-techtree-revision", BuildInfo.source_revision())
  end
end
