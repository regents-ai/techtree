defmodule TechtreeWeb.Components.Marketing do
  @moduledoc """
  The marketing site's shared pieces: the dark opening band every inner page
  starts with, a moving picture over the still the stylesheet draws, and a
  service's price level. The
  home page and the inner pages use the same ones; their styles are in
  `assets/css/techtree_home.css` and `assets/css/techtree_marketing.css`, and
  their motion is the hooks in `assets/js/marketing`.
  """

  use TechtreeWeb, :html

  alias TechtreeWeb.Components.BookCall

  attr :id, :string, default: "opening"
  attr :eyebrow, :string, required: true
  attr :title, :string, required: true
  attr :line, :string, required: true, doc: "the page's promise, one sentence"
  attr :more, :string, default: nil, doc: "a second, quieter paragraph under the promise"
  attr :shape, :integer, default: nil, doc: "the dot picture's shape (SHAPES in scenes.ts)"
  attr :icon, :string, default: nil, doc: "the Lucide icon the still picture shows"

  attr :service, :string,
    default: nil,
    doc: "a service's id: its picture is the service's contour lines in its own colours"

  attr :rise, :boolean,
    default: true,
    doc:
      "the title's words rise on the first visit; false for a title that can change, which can then take focus"

  attr :book_call, :boolean, default: true

  slot :actions, doc: "the page's primary action, before Book Call"
  slot :inner_block, doc: "anything under the actions"

  @doc """
  The dark band that opens an inner page: an eyebrow, the page's name, its
  promise in one sentence, its primary action beside Book Call, and a moving
  picture of the page's own: a dot screen drawing the page's shape, or a
  service's contour lines. The parts settle in once as the site first opens
  (`mountEntrance` in `assets/js/marketing/reveal.ts`).
  """
  def opening(assigns) do
    assigns = assign(assigns, :picture?, assigns.shape != nil or assigns.service != nil)

    ~H"""
    <section
      id={@id}
      class={["mk-opening", "mk-dark", @picture? && "mk-opening--picture"]}
      aria-labelledby={"#{@id}-title"}
      data-entrance
    >
      <div class="mk-opening__copy">
        <p class="mk-eyebrow" data-entrance-part data-markdown-skip>{@eyebrow}</p>
        <h1
          :if={@rise}
          id={"#{@id}-title"}
          class="mk-opening__title"
          phx-update="ignore"
          data-entrance-display
        >
          {@title}
        </h1>
        <h1
          :if={!@rise}
          id={"#{@id}-title"}
          class="mk-opening__title"
          tabindex="-1"
          data-entrance-part
        >
          {@title}
        </h1>
        <p class="mk-opening__line" data-entrance-part>{@line}</p>
        <p :if={@more} class="mk-opening__more" data-entrance-part>{@more}</p>
        <div
          :if={@actions != [] or @book_call}
          class="mk-opening__actions"
          data-entrance-part
          data-markdown-skip
        >
          {render_slot(@actions)}
          <BookCall.book_call :if={@book_call} variant={:secondary} />
        </div>
        {render_slot(@inner_block)}
      </div>
      <.field
        :if={@picture?}
        id={"#{@id}-picture"}
        scene={if @service, do: "backdrop", else: "screen"}
        shape={@shape}
        class={["mk-opening__picture", @service && "mk-service--#{@service}"]}
      >
        <Regent.Icons.icon :if={@icon} name={@icon} class="mk-opening__glyph" />
      </.field>
    </section>
    """
  end

  attr :level, :integer, values: [1, 2, 3, 4], required: true
  attr :id, :string, default: nil

  @doc """
  A service's price level: four diamonds, the first `level` of them filled,
  beside the word Price. It is never a figure. Its name says the level in
  words, and the marks are hidden from screen readers.
  """
  def price(assigns) do
    ~H"""
    <div id={@id} class="mk-price" role="img" aria-label={"Price level #{@level} of 4"}>
      <span class="mk-price__label" aria-hidden="true">Price</span>
      <span class="mk-price__marks" aria-hidden="true">
        <span :for={mark <- 1..4} class={["mk-price__mark", mark <= @level && "mk-price__mark--on"]}></span>
      </span>
    </div>
    """
  end

  attr :id, :string, required: true
  attr :scene, :string, values: ~w(glow screen mark backdrop), required: true
  attr :shape, :integer, default: nil
  attr :class, :any, default: nil
  slot :inner_block

  @doc """
  A moving picture (`assets/js/marketing/field_hook.ts`) over the still the
  stylesheet draws, which stays for less motion and where WebGPU is missing.
  """
  def field(assigns) do
    ~H"""
    <div
      id={@id}
      class={["mk-field", "mk-field--#{@scene}", @class]}
      phx-hook="MarketingField"
      phx-mounted={JS.ignore_attributes(["data-field-ready"])}
      data-field={@scene}
      data-field-shape={@shape}
      aria-hidden="true"
    >
      <div class="mk-field__still">{render_slot(@inner_block)}</div>
      <canvas id={"#{@id}-canvas"} class="mk-field__canvas" phx-update="ignore" data-field-canvas></canvas>
    </div>
    """
  end
end
