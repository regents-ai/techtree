defmodule TechtreeWeb.SkillController do
  @moduledoc """
  The Techtree skill at `/skill.md`: the repository's `skills/techtree/SKILL.md`,
  byte for byte, the same file `npx skills add regents-ai/techtree --skill
  techtree` installs. It is compiled in; the image carries it at `/skills`.
  """

  use TechtreeWeb, :controller

  @path Path.expand("../../../../skills/techtree/SKILL.md", __DIR__)
  @external_resource @path
  @skill File.read!(@path)

  def show(conn, _params) do
    conn
    |> put_resp_content_type("text/markdown", "utf-8")
    |> send_resp(200, @skill)
  end
end
