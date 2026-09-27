defmodule TechtreeWeb.AgentGuideController do
  @moduledoc """
  The agent guide at `/llms.txt`, written in `priv/pages/llms.txt` with its
  browser tool table filled in from the tool manifest.
  """

  use TechtreeWeb, :controller

  @path Path.expand("../../../priv/pages/llms.txt", __DIR__)
  @external_resource @path
  @guide @path |> File.read!() |> String.replace("{{tools}}", TechtreeWeb.Tools.markdown_table())

  def show(conn, _params) do
    conn
    |> put_resp_content_type("text/plain")
    |> put_resp_header("cache-control", "public")
    |> send_resp(200, @guide)
  end
end
