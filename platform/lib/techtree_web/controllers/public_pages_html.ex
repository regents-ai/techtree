defmodule TechtreeWeb.PublicPagesHTML do
  @moduledoc "About, Contact and Privacy, in the site's document layout."

  use TechtreeWeb, :html

  attr :page, :map, required: true

  def show(assigns) do
    ~H"""
    <Layouts.page>
      <header class="editorial-heading">
        <h1>{@page.title}</h1>
        <p class="lede">{@page.lede}</p>
      </header>
      <article class="rg-blog__prose">
        {raw(@page.body_html)}
      </article>
    </Layouts.page>
    """
  end
end
