defmodule TechtreeWeb.Layouts do
  @moduledoc """
  The restrained frame shared by the Techtree public surface.
  """

  use TechtreeWeb, :html

  embed_templates "layouts/*"

  @doc """
  Wrap one page.
  """
  attr :wide, :boolean, default: false, doc: "give the page the wider measure"
  attr :flush, :boolean, default: false, doc: "let a page own its vertical rhythm"
  slot :inner_block, required: true

  def page(assigns) do
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
          <a href="https://github.com/regents-ai">GitHub</a>
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
      <span>A Regents Labs project</span>
      <span>Local by default. Proofs publish only by deliberate release.</span>
    </footer>
    """
  end
end
