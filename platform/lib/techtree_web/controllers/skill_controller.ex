defmodule TechtreeWeb.SkillController do
  @moduledoc """
  The Techtree skill at `/skill.md`: the repository's `skills/techtree/SKILL.md`,
  byte for byte, the same file `npx skills add regents-ai/techtree --skill
  techtree` installs. It is compiled in; the image carries it at `/skills`, as
  it carries the blog at `/blog`.

  Its sections from "What to watch" on also close the agent guide at
  `/agents.md` (`TechtreeWeb.AgentsController`), so the two say the same.
  """

  use TechtreeWeb, :controller

  @path Path.expand("../../../../skills/techtree/SKILL.md", __DIR__)
  @external_resource @path
  @skill File.read!(@path)
  [_connect, watch] = String.split(@skill, "\n## What to watch\n")
  @shared_sections "## What to watch\n" <> watch

  def show(conn, _params) do
    conn
    |> put_resp_content_type("text/markdown", "utf-8")
    |> send_resp(200, @skill)
  end

  @doc """
  The skill from "What to watch" to its last line.
  """
  @spec shared_sections() :: String.t()
  def shared_sections, do: @shared_sections
end
