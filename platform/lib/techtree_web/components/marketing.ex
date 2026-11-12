defmodule TechtreeWeb.Components.Marketing do
  @moduledoc """
  The marketing site's shared pieces: the dark opening band every inner page
  starts with, a moving picture over the still the stylesheet draws, and a
  group of items one open at a time beside a dot picture. The home page and
  the inner pages use the same ones; their styles are in
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
      phx-mounted={JS.ignore_attributes(["data-field-ready", "data-field-shape"])}
      data-field={@scene}
      data-field-shape={@shape}
      aria-hidden="true"
    >
      <div class="mk-field__still">{render_slot(@inner_block)}</div>
      <canvas id={"#{@id}-canvas"} class="mk-field__canvas" phx-update="ignore" data-field-canvas></canvas>
    </div>
    """
  end

  attr :id, :string, required: true
  attr :name, :string, required: true
  attr :line, :string, required: true
  attr :flip, :boolean, default: false, doc: "put the picture before the items"

  slot :item, required: true do
    attr :title, :string, required: true
    attr :icon, :string, required: true
    attr :shape, :integer, required: true, doc: "the dot picture's shape (SHAPES in scenes.ts)"
    attr :capability, :atom
    attr :open, :boolean
    attr :id, :string
  end

  @doc """
  One group of items, one open at a time, beside a dot picture that draws the
  open item's shape (`assets/js/marketing/accordion.ts`).
  """
  def group(assigns) do
    assigns = assign(assigns, :first, Enum.find(assigns.item, & &1[:open]) || hd(assigns.item))

    ~H"""
    <section
      id={@id}
      class={["mk-section", "mk-group", @flip && "mk-group--flip"]}
      aria-labelledby={"#{@id}-title"}
      phx-hook="MarketingAccordion"
    >
      <div class="mk-group__items">
        <h2 id={"#{@id}-title"}>{@name}</h2>
        <p class="mk-group__line">{@line}</p>
        <details
          :for={{item, index} <- Enum.with_index(@item)}
          id={item[:id] || "#{@id}-#{index}"}
          class="mk-item"
          name={@id}
          open={item[:open]}
          data-shape={item.shape}
          phx-mounted={JS.ignore_attributes(["open"])}
        >
          <summary class="mk-item__summary">
            <Regent.Icons.icon name={item.icon} class="mk-item__icon" />
            <h3 class="mk-item__title">{item.title}</h3>
            <.capability_status :if={item[:capability]} capability={item.capability} />
            <Regent.Icons.icon name="plus" class="mk-item__toggle" />
          </summary>
          <div class="mk-item__body" data-item-body>
            {render_slot(item)}
          </div>
        </details>
      </div>
      <.field id={"#{@id}-picture"} scene="screen" shape={@first.shape} class="mk-group__picture">
        <Regent.Icons.icon
          :for={item <- @item}
          name={item.icon}
          class="mk-group__glyph"
          data-glyph={item.shape}
        />
      </.field>
    </section>
    """
  end
end
