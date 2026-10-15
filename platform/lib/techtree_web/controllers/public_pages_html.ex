defmodule TechtreeWeb.PublicPagesHTML do
  @moduledoc "About, Contact, Privacy and Terms, in the site's document layout."

  use TechtreeWeb, :html

  attr :page, :map, required: true

  # PublicDocuments.page/1 renders committed Markdown at compile time; no request HTML enters it.
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
end
