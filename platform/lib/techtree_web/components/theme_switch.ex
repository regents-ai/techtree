defmodule TechtreeWeb.Components.ThemeSwitch do
  @moduledoc """
  The light and dark theme switch. Signed in, it is a row of the account menu;
  signed out, it sits in the header beside Sign in (`TechtreeWeb.AccountMenuLive`
  draws one or the other, never both).
  """
  use TechtreeWeb, :html

  # The moon and the sun, a "#" for each block. Every block of the moon flies to
  # one of the sun, so they have as many, on one square grid whose outer ring
  # stays clear (the glass knob's bevel lies over it).
  @moon [
    ".............",
    "....##.......",
    "...##.....#..",
    "..##.........",
    ".###.........",
    ".###.....#...",
    ".###.........",
    ".#####.......",
    ".######......",
    "..#########..",
    "...#######...",
    "....#####....",
    "............."
  ]

  @sun [
    ".............",
    ".#....#....#.",
    "..#.......#..",
    ".....###.....",
    "....#####....",
    "...#######...",
    ".#.#######.#.",
    "...#######...",
    "....#####....",
    ".....###.....",
    "..#.......#..",
    ".#....#....#.",
    "............."
  ]

  block_count = fn rows ->
    rows |> Enum.join() |> :binary.matches("#") |> length()
  end

  if block_count.(@moon) != block_count.(@sun) do
    raise ArgumentError, "the theme switch's moon and sun need as many blocks"
  end

  for rows <- [@moon, @sun] do
    if Enum.any?(rows, &(String.length(&1) != length(rows))) do
      raise ArgumentError, "the theme switch's pictures are square"
    end

    ring = [hd(rows), List.last(rows) | Enum.map(rows, &(String.first(&1) <> String.last(&1)))]

    if Enum.any?(ring, &String.contains?(&1, "#")) do
      raise ArgumentError, "the theme switch's pictures keep their outer ring clear"
    end
  end

  attr :id, :string, required: true
  attr :class, :any, default: nil

  @doc """
  The light and dark theme switch: a button with the role of a switch, on for
  the light theme, with a knob that slides from night on the left to day on the
  right. A press, Enter or Space turns it, and the knob can be dragged; it
  settles on the nearer side when let go.

  The server draws a still face: a flat square track and knob with the moon or
  the sun, each a picture of tiny square blocks, placed for the theme showing. Once
  the browser has drawn a first frame of the glass knob, with the same blocks
  behind it and its light, on the canvas inside (`assets/js/hooks/theme_switch.ts`,
  `assets/js/theme_switch/`), that picture takes over. Without WebGPU, with less
  motion asked for or in forced colours the still face stays, and it is a whole
  working switch on its own.

  The browser owns the press: it writes the theme cookie the server reads on
  the next render (`assets/js/theme.ts`), so the switch is left out of LiveView's
  patching, and the attributes the browser writes on it are kept.
  """
  def theme_switch(assigns) do
    assigns = assign(assigns, moon: @moon, sun: @sun)

    ~H"""
    <div
      id={@id}
      class={["theme-switch", @class]}
      phx-hook="ThemeSwitch"
      phx-update="ignore"
      phx-mounted={JS.ignore_attributes(["data-theme-switch-ready", "style"])}
      data-theme-switch
    >
      <button
        id={"#{@id}-button"}
        class="theme-switch__button"
        type="button"
        role="switch"
        aria-checked="false"
        aria-label="Light theme"
      >
        <span class="theme-switch__still" aria-hidden="true">
          <span class="theme-switch__track" data-theme-switch-track>
            <span class="theme-switch__knob" data-theme-switch-knob>
              <.blocks rows={@moon} class="theme-switch__moon" />
              <.blocks rows={@sun} class="theme-switch__sun" />
            </span>
          </span>
        </span>
        <canvas class="theme-switch__canvas" data-theme-switch-canvas aria-hidden="true"></canvas>
      </button>
    </div>
    """
  end

  attr :rows, :list, required: true
  attr :class, :string, required: true

  # One of the switch's pictures, a block for each "#", one unit square apiece
  # with a hairline between neighbours.
  defp blocks(assigns) do
    assigns =
      assign(assigns,
        size: length(assigns.rows),
        blocks:
          for(
            {row, y} <- Enum.with_index(assigns.rows),
            {"#", x} <- Enum.with_index(String.graphemes(row)),
            do: {x, y}
          )
      )

    ~H"""
    <svg
      class={@class}
      viewBox={"0 0 #{@size} #{@size}"}
      shape-rendering="crispEdges"
      aria-hidden="true"
    >
      <g transform="translate(0.06 0.06)">
        <rect :for={{x, y} <- @blocks} x={x} y={y} width="0.88" height="0.88" />
      </g>
    </svg>
    """
  end
end
