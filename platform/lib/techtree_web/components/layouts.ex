defmodule TechtreeWeb.Layouts do
  @moduledoc """
  The frame every page is read inside: a name, three ways on, and one line at
  the bottom saying whose project this is.

  The way out to the source is the only link here that could ever move, so it
  is not written down. It is read from the release this site is publishing, and
  it appears only once that release names one immutable revision — a reader who
  follows it a year from now reaches the code this page was describing.
  """

  use TechtreeWeb, :html

  alias TechtreeWeb.ReleaseInfo

  embed_templates "layouts/*"

  @doc """
  Wrap one page.
  """
  attr :wide, :boolean, default: false, doc: "give the page the wider measure"
  attr :flush, :boolean, default: false, doc: "let a page own its vertical rhythm"
  slot :inner_block, required: true

  def page(assigns) do
    assigns = assign_new(assigns, :repository_url, &repository_url/0)

    ~H"""
    <header class="masthead">
      <div class="masthead__inner">
        <a class="masthead__name" href={~p"/"} aria-label="Techtree home">
          <span class="masthead__mark" aria-hidden="true">
            <span></span><span></span><span></span><span></span><span></span>
          </span>
          <span>Techtree</span>
        </a>
        <nav class="masthead__nav" aria-label="Sections">
          <a :if={@repository_url} class="masthead__source" href={@repository_url}>GitHub</a>
          <a href={~p"/docs"}>Docs</a>
          <a class="masthead__proof" href={~p"/proofs"}>View a proof</a>
        </nav>
      </div>
    </header>

    <main class={["page", @wide && "page--wide", @flush && "page--flush"]}>
      <p class="notice" role="status">
        The connection to the site dropped. The page will reconnect on its own.
      </p>
      {render_slot(@inner_block)}
    </main>

    <footer class="colophon">
      <span class="colophon__mark" aria-hidden="true"></span>
      <span>A Regents Labs project</span>
    </footer>
    """
  end

  defp repository_url do
    case ReleaseInfo.current() do
      %{repository_url: url} -> url
      nil -> nil
    end
  end
end
