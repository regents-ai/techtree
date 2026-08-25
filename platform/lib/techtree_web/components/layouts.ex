defmodule TechtreeWeb.Layouts do
  @moduledoc """
  The frame every page is read inside: a name, a short way to the other pages,
  and one line at the bottom saying what this site is and is not.
  """

  use TechtreeWeb, :html

  embed_templates "layouts/*"

  @doc """
  Wrap one page.
  """
  attr :wide, :boolean, default: false, doc: "give the page the wider measure"
  slot :inner_block, required: true

  def page(assigns) do
    ~H"""
    <header class="masthead">
      <div class="masthead__inner">
        <a class="masthead__name" href={~p"/"}>Techtree Climb</a>
        <nav class="masthead__nav" aria-label="Sections">
          <a href={~p"/start"}>Start</a>
          <a href={~p"/climbs"}>Climbs</a>
          <a href={~p"/proofs/local"}>Local results</a>
          <a href={~p"/protocol"}>Protocol</a>
        </nav>
      </div>
    </header>

    <main class={["page", @wide && "page--wide"]}>
      <p class="notice" role="status">
        The connection to the site dropped. The page will reconnect on its own.
      </p>
      {render_slot(@inner_block)}
    </main>

    <footer class="colophon">
      Techtree Climb publishes the public Climbs and the documents behind them.
      Trials run on the participant's own machine; this site does not run them,
      and does not receive their results.
    </footer>
    """
  end
end
