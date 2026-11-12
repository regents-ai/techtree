defmodule TechtreeWeb.Components.ValueCards do
  @moduledoc """
  Value cards: a row of cards for a home page or any other section, shown at
  `/animations/cards`. Every site takes this same row and gives it its own cards.

  A card is dark in both themes. From the top: a square panel of small coloured
  glyphs that moves and follows a mouse, drawn on the GPU by the `ValueCard`
  hook (`assets/js/hooks/value_card.ts`); the card's name in its colour beside
  its place in the row; one line saying what it is for; a sentence; and, under
  a dashed rule, where the card goes.

  A still frame of the same panel (`priv/static/images/value-cards/<id>.webp`)
  is the picture until the panel has drawn, and stays where it cannot be: no
  WebGPU, no JavaScript, or a visitor who asked for less motion.

  Each card is a map:

    * `:id` - the panel's name, a file in `assets/js/value_cards/panels/`
    * `:name` - one or two words
    * `:headline` - one line, ending with a full stop
    * `:line` - one sentence
    * `:tint` - the colour the name takes, reading at 4.5:1 on the card's
      `#0b0b0c`: the panel's main colour, or a lighter step of it
    * `:action` - two words for where the card goes
    * one of `:href`, another site's address, which opens in a new tab;
      `:navigate`, another page of this site; or `:patch`, another page of the
      same LiveView, such as the app shell

  ## Your own cards

  Take the row as it is: this module, `assets/css/components/value_cards.css`
  (imported in `app.css`), the `ValueCard` hook (registered with the hooks of
  the pages that show the row), and `assets/js/value_cards/`: `panel.ts`,
  `renderer.ts`, `shared_device.ts` and `stills.mjs` stay as they are;
  `index.ts` and `panels/` are yours. Add `"stills:value-cards": "node
  assets/js/value_cards/stills.mjs"` to `package.json`.

  For each card, write its panel as one file in `panels/` (colours deep, main
  and bright; the size of one glyph cell; the second its still frame shows; and
  the shader body, which colours only through `ramp` and ends with `emit`; the
  template's six are the examples), list it in `index.ts`, and remove the
  template's six you do not use, with their stills. Then draw the stills from
  `platform/` on a machine with a GPU: `npm run stills:value-cards`, or
  `npm run stills:value-cards -- <name>` for one. They land in
  `priv/static/images/value-cards/`. Draw a panel's still again whenever it or
  `panel.ts` changes, so the still always matches the moving panel.
  """

  use Phoenix.Component
  use TechtreeWeb, :verified_routes

  alias Phoenix.LiveView.JS

  attr :id, :string, required: true
  attr :label, :string, required: true, doc: "names the row for screen readers"
  attr :cards, :list, required: true

  def value_cards(assigns) do
    assigns = assign(assigns, :count, length(assigns.cards))

    ~H"""
    <ul id={@id} class="value-cards" aria-label={@label}>
      <li
        :for={{card, number} <- Enum.with_index(@cards, 1)}
        id={"#{@id}-#{card.id}"}
        class="value-cards__card"
        style={"--value-card-tint: #{card.tint}"}
        phx-hook="ValueCard"
        phx-mounted={JS.ignore_attributes(["data-value-card-ready"])}
        data-value-card={card.id}
      >
        <a
          :if={card[:href]}
          href={card.href}
          target="_blank"
          rel="noopener noreferrer"
          class="value-cards__face"
        >
          <.face id={"#{@id}-#{card.id}"} card={card} place={place(number, @count)} away />
        </a>
        <.link
          :if={!card[:href]}
          navigate={card[:navigate]}
          patch={card[:patch]}
          class="value-cards__face"
        >
          <.face id={"#{@id}-#{card.id}"} card={card} place={place(number, @count)} />
        </.link>
      </li>
    </ul>
    """
  end

  attr :id, :string, required: true
  attr :card, :map, required: true
  attr :place, :string, required: true
  attr :away, :boolean, default: false

  defp face(assigns) do
    ~H"""
    <div class="value-cards__panel" aria-hidden="true">
      <img
        class="value-cards__still"
        src={~p"/images/value-cards/#{@card.id <> ".webp"}"}
        alt=""
        width="600"
        height="600"
        loading="lazy"
        decoding="async"
      />
      <div id={"#{@id}-stage"} class="value-cards__stage" phx-update="ignore">
        <canvas data-value-card-canvas></canvas>
      </div>
    </div>
    <div class="value-cards__words">
      <div class="value-cards__meta">
        <p class="value-cards__name">{@card.name}</p>
        <span class="value-cards__place" aria-hidden="true">{@place}</span>
      </div>
      <p class="value-cards__headline">{@card.headline}</p>
      <p class="value-cards__line">{@card.line}</p>
      <p class="value-cards__action">
        {@card.action}<span :if={@away} class="visually-hidden">, opens in a new tab</span>
        <Regent.Icons.icon
          name={if @away, do: "arrow-up-right", else: "arrow-right"}
          class="value-cards__arrow"
        />
      </p>
    </div>
    """
  end

  # A card's place in its row, as "01 / 06".
  defp place(number, count), do: "#{two(number)} / #{two(count)}"

  defp two(number), do: number |> Integer.to_string() |> String.pad_leading(2, "0")
end
