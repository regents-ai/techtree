defmodule TechtreeWeb.Components.PageHead do
  @moduledoc """
  The title row every page inside the shell opens with: the page's name, an
  optional tip that explains it, and the page's own actions on the right.
  Explanations live in the tip, never in a paragraph under the title.
  """

  use Phoenix.Component

  attr :title, :string, required: true
  attr :id, :string, default: "page-title"
  slot :tip, doc: "one or two sentences on what the page is for"
  slot :actions, doc: "the page's own buttons or links"

  def page_head(assigns) do
    ~H"""
    <header class="page-head">
      <h1 id={@id} tabindex="-1">{@title}</h1>
      <Regent.Primitives.tip :if={@tip != []} id={"#{@id}-tip"} label={"About #{@title}"}>
        {render_slot(@tip)}
      </Regent.Primitives.tip>
      <div :if={@actions != []} class="page-head__actions">{render_slot(@actions)}</div>
    </header>
    """
  end

  attr :id, :string, required: true
  slot :inner_block, required: true, doc: "one short line, such as \"Sign in to keep notes.\""

  @doc "What a signed-out visitor sees in place of a page that needs an account."
  def signed_out(assigns) do
    ~H"""
    <section id={@id} class="page-signed-out">
      <p>{render_slot(@inner_block)}</p>
      <Regent.Primitives.button type="button" data-account-target="sign-in">
        Sign in
      </Regent.Primitives.button>
    </section>
    """
  end
end
