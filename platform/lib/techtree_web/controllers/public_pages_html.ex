defmodule TechtreeWeb.PublicPagesHTML do
  @moduledoc """
  Privacy, Terms and Security's sample report in the site's document layout,
  and About and the agents' pages under the marketing site's opening band.
  """

  use TechtreeWeb, :html

  import TechtreeWeb.Components.Marketing, only: [opening: 1]

  attr :page, :map, required: true

  # PublicDocuments.page/1 renders only committed Markdown; no request HTML enters it.
  # sobelow_skip ["XSS.Raw"]
  def show(assigns) do
    ~H"""
    <Layouts.page>
      <header class="editorial-heading">
        <h1>{@page.title}</h1>
        <p class="lede">{@page.lede}</p>
      </header>
      <article class="public-document rg-blog__prose">
        {raw(@page.body_html)}
      </article>
    </Layouts.page>
    """
  end

  attr :page, :map, required: true

  # About, its one line as the band's promise; PublicDocuments.page/1 renders
  # only committed Markdown.
  # sobelow_skip ["XSS.Raw"]
  def about(assigns) do
    ~H"""
    <Layouts.page wide flush>
      <.opening eyebrow="Company" title={@page.title} line={@page.lede} shape={8} icon="building-2" />
      <section class="mk-section">
        <article class="public-document rg-blog__prose">
          {raw(@page.body_html)}
        </article>
      </section>
    </Layouts.page>
    """
  end

  attr :page, :map, required: true

  # The list of agents or one agent's page; PublicDocuments.page/1 renders only
  # committed Markdown, filled with this site's own address.
  # sobelow_skip ["XSS.Raw"]
  def agent(assigns) do
    ~H"""
    <Layouts.page wide flush>
      <.opening eyebrow="Agents" title={@page.title} line={@page.lede} shape={1} icon="bot">
        <:actions>
          <a href={~p"/account/agents"} class="rg-button rg-button--primary">Pair</a>
        </:actions>
      </.opening>
      <section class="mk-section">
        <article class="public-document rg-blog__prose">
          {raw(@page.body_html)}
        </article>
      </section>
    </Layouts.page>
    """
  end
end
