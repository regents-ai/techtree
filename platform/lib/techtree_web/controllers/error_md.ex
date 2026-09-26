defmodule TechtreeWeb.ErrorMD do
  @moduledoc """
  What a request that asked for Markdown is told when it reaches no page. A
  missing page answers with a short map of the site, so an agent that followed
  a stale link can find its way without guessing.
  """

  alias TechtreeWeb.MD

  @map """
  ## Where to go instead

  - [Home](/): what Techtree is and how to start
  - [Start](/start): try the example Climb, evaluate your own Skill, or build tasks from your repository
  - [Results](/results): published Results, newest first
  - [Docs](/docs): install, run, verify, publish and integrate
  - [OpenAPI description](/openapi.json): every public API address, typed
  - [Agent guide](/llms.txt): when to use Techtree and where everything is
  - [Sitemap](/sitemap.xml): every public page
  """

  @doc "Render a status-code template as a Markdown document."
  def render("404.md", _assigns) do
    """
    # This page is not part of Techtree.

    The link may be old or mistyped.

    #{@map}#{MD.trailer()}\
    """
  end

  def render("500.md", _assigns) do
    """
    # Techtree could not load this page.

    Something went wrong on our side. Try again in a moment.

    #{@map}#{MD.trailer()}\
    """
  end

  def render(template, _assigns) do
    "# " <>
      Phoenix.Controller.status_message_from_template(template) <> "\n\n" <> @map <> MD.trailer()
  end
end
