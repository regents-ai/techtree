defmodule TechtreeWeb.ResultShareCard do
  @moduledoc """
  The picture a shared link to a published Result shows on X and other sites,
  in the site picture's Canopy frame: the Climb's name, the verdict in large
  type and how many tasks the Result ran on, with three tiles on the right for
  the tasks that went better, stayed the same and went worse.

  Every word on the left sits in the part of the picture that X's phone view
  keeps (the left 640 or so of its 1200) and clear of the bottom-left corner,
  where X lays the site's name. The Climb's name is the site's own
  (`TechtreeWeb.ResultNames`); the publisher's name for the Skill is never
  drawn, since nothing checks it.

  A withdrawn Result says so under the verdict, and its picture's address
  changes with the withdrawal, so a site that keeps pictures by address
  fetches the new one.
  """

  use TechtreeWeb, :verified_routes

  alias Techtree.Network.Query
  alias TechtreeWeb.{ResultAssessment, ResultNames}
  alias Vix.Vips.{Image, Operation}

  @width 1200
  @height 630

  # The panel is inset from the picture's edge, with its top-left and
  # bottom-right corners cut.
  @inset 36
  @cut 28

  # The words on the left. Each layer of words is as tall as its letters, so
  # the gaps between them are measured from letter to letter.
  @left 56
  @words_w 584
  @eyebrow_top 156
  @h1_size 76
  @h1_line 73
  @h1_gap 34
  @lede_w 560

  # The three tiles on the right.
  @tiles_x 680
  @tiles_w 464
  @tiles_top 132
  @tiles_bottom 558
  @tile_gap 14
  @tile_pad 26
  @tile_line_gap 14

  @ground "#1E6B45"
  @edge "#DCE3D6"
  @face "#FAFBF7"
  @ink "#0F1B14"
  @muted "#5F6761"
  @dot "#2FA866"
  @tangerine "#FF5B19"
  @powder "#AECACD"
  @lime "#C8F25C"

  # Better, the same and worse, top to bottom.
  @tile_fills [@ground, "#D2E4D5", "#E6ECE2"]

  # The Regents crown: its squares on a 178 x 106 grid.
  @crown_box {31, 46, 178, 106}
  @crown_squares [{31, 46}, {103, 46}, {175, 46}] ++
                   for(y <- [82, 118], x <- [31, 67, 103, 139, 175], do: {x, y})

  @doc """
  Where a Result's picture is served. A withdrawn Result's address carries
  `v=withdrawn`, so it differs from the one shared before the withdrawal.
  """
  @spec image_url(map()) :: String.t()
  def image_url(entry) do
    if Query.withdrawn?(entry),
      do: url(~p"/results/#{entry.bundle_digest}/share.png?#{[v: "withdrawn"]}"),
      else: url(~p"/results/#{entry.bundle_digest}/share.png")
  end

  @doc "What the picture shows, in words, for a reader that cannot see it."
  @spec alt(map()) :: String.t()
  def alt(entry) do
    assessment = entry.assessment

    withdrawn(entry) <>
      "#{ResultNames.campaign(entry)}: #{ResultAssessment.verdict_label(assessment)} on " <>
      "#{tasks(entry.task_count)}, #{assessment.wins} better, #{assessment.ties} same, " <>
      "#{assessment.losses} worse."
  end

  defp withdrawn(entry),
    do: if(Query.withdrawn?(entry), do: "Withdrawn by the participant. ", else: "")

  @doc """
  A Result's picture as PNG bytes, 1200 by 630. It is drawn from a few
  words the site chooses, so only a fault in the drawing library stops it,
  and that raises.
  """
  @spec png(map()) :: binary()
  def png(entry) do
    {words, eyebrow_middle} = words(entry)
    {canvas, _flags} = Operation.svgload_buffer!(svg(eyebrow_middle))

    (words ++ tile_words(entry.assessment))
    |> Enum.reduce(canvas, &place/2)
    |> Operation.pngsave_buffer!()
  end

  # The site's name, the Climb's name, the verdict and the task count, each
  # placed under the one before it, and the middle of the Climb's name, where
  # the dot before it sits.
  defp words(entry) do
    eyebrow = entry |> ResultNames.campaign() |> plain() |> String.upcase()
    verdict = ResultAssessment.verdict_label(entry.assessment)
    lede = withdrawn(entry) <> "#{tasks(entry.task_count)}, with and without the Skill."

    site = layer("TECHTREE.SH", :mono, 17, @muted)
    eyebrow = fit(eyebrow, :mono, 17, @muted, @words_w - 24)
    lines = wrap(verdict, :pixel, @h1_size, @ink, @words_w)
    lede = layer(lede, :regular, 25, @muted, width: @lede_w)

    h1_top = @eyebrow_top + Image.height(eyebrow) + @h1_gap
    lede_top = h1_top + length(lines) * @h1_line + 24
    h1 = Enum.with_index(lines, fn line, index -> {line, {@left, h1_top + index * @h1_line}} end)

    {[{site, {156, 73}}, {eyebrow, {@left + 24, @eyebrow_top}}] ++
       h1 ++ [{lede, {@left, lede_top}}], @eyebrow_top + div(Image.height(eyebrow), 2)}
  end

  defp tiles(assessment) do
    [
      {"#{assessment.wins} better", "Better with the Skill", @lime, "#FFFFFF"},
      {"#{assessment.ties} same", "No change", @ink, @ink},
      {"#{assessment.losses} worse", "Worse with the Skill", @ink, @ink}
    ]
  end

  # Each tile's count and words, centred down the tile.
  defp tile_words(assessment) do
    assessment
    |> tiles()
    |> Enum.with_index()
    |> Enum.flat_map(fn {{count, words, count_color, color}, index} ->
      count = layer(count, :pixel, 36, count_color)
      words = layer(words, :regular, 20, color)
      {top, height} = tile(index)

      count_top =
        top + div(height - Image.height(count) - @tile_line_gap - Image.height(words), 2)

      x = @tiles_x + @tile_pad

      [{count, {x, count_top}}, {words, {x, count_top + Image.height(count) + @tile_line_gap}}]
    end)
  end

  defp tile(index) do
    height = div(@tiles_bottom - @tiles_top - 2 * @tile_gap, 3)
    {@tiles_top + index * (height + @tile_gap), height}
  end

  defp svg(eyebrow_middle) do
    tiles =
      @tile_fills
      |> Enum.with_index()
      |> Enum.map_join(fn {fill, index} ->
        {top, height} = tile(index)

        ~s|<rect x="#{@tiles_x + 0.5}" y="#{top + 0.5}" width="#{@tiles_w - 1}" height="#{height - 1}" fill="#{fill}" stroke="#{@ink}" stroke-width="1"/>|
      end)

    """
    <svg xmlns="http://www.w3.org/2000/svg" width="#{@width}" height="#{@height}">
      <rect width="#{@width}" height="#{@height}" fill="#{@ground}"/>
      <polygon points="#{panel(0, @cut)}" fill="#{@edge}"/>
      <polygon points="#{panel(1, @cut - 0.4)}" fill="#{@face}"/>
      <rect x="#{@inset - 6}" y="#{@inset + 12}" width="40" height="4" fill="#{@tangerine}"
        transform="rotate(-45 #{@inset + 14} #{@inset + 14})"/>
      <rect x="#{@width - @inset - 34}" y="#{@height - @inset - 16}" width="40" height="4"
        fill="#{@powder}" transform="rotate(-45 #{@width - @inset - 14} #{@height - @inset - 14})"/>
      #{crown_svg(@left, 62, 76)}
      <rect x="#{@left}" y="#{eyebrow_middle - 6}" width="12" height="12" fill="#{@dot}"/>
      #{tiles}
    </svg>
    """
  end

  # The panel's outline, `inset` in from its edge, with two corners cut.
  defp panel(inset, cut) do
    {left, top} = {@inset + inset, @inset + inset}
    {right, bottom} = {@width - @inset - inset, @height - @inset - inset}

    Enum.map_join(
      [
        {left + cut, top},
        {right, top},
        {right, bottom - cut},
        {right - cut, bottom},
        {left, bottom},
        {left, top + cut}
      ],
      " ",
      fn {x, y} -> "#{x},#{y}" end
    )
  end

  # The crown `width` wide with its top left at `x`, `y`.
  defp crown_svg(x, y, width) do
    {left, top, box_w, _box_h} = @crown_box

    squares =
      Enum.map_join(@crown_squares, fn {sx, sy} ->
        ~s|<rect x="#{sx}" y="#{sy}" width="34" height="34"/>|
      end)

    ~s|<g fill="#{@ink}" transform="translate(#{x} #{y}) scale(#{width / box_w}) translate(#{-left} #{-top})">#{squares}</g>|
  end

  defp place({layer, {x, y}}, picture),
    do: Operation.composite2!(picture, layer, :VIPS_BLEND_MODE_OVER, x: x, y: y)

  # The words as lines no wider than `max`, broken between words: a word
  # joins the last line while the two still fit, and starts the next line
  # when they do not.
  defp wrap(words, weight, size, color, max) do
    [first | rest] = String.split(words, " ")

    rest
    |> Enum.reduce([first], fn word, [line | done] ->
      longer = line <> " " <> word

      if Image.width(layer(longer, weight, size, color)) <= max,
        do: [longer | done],
        else: [word, line | done]
    end)
    |> Enum.reverse()
    |> Enum.map(&layer(&1, weight, size, color))
  end

  # The words on one line no wider than `max`, cut short with an ellipsis
  # where they run over. The first cut keeps the share of the words that fits,
  # so a long name takes a few drawings, not one for each letter it loses.
  defp fit(words, weight, size, color, max) do
    layer = layer(words, weight, size, color)

    if Image.width(layer) <= max do
      layer
    else
      graphemes = String.graphemes(words)
      keep = min(div(length(graphemes) * max, Image.width(layer)), length(graphemes) - 1)
      cut(graphemes, keep, {weight, size, color, max})
    end
  end

  defp cut(graphemes, keep, {weight, size, color, max} = style) do
    shown = (graphemes |> Enum.take(keep) |> Enum.join() |> String.trim_trailing()) <> "…"
    layer = layer(shown, weight, size, color)

    if Image.width(layer) <= max or keep <= 1,
      do: layer,
      else: cut(graphemes, keep - 1, style)
  end

  # The mono words are spaced 0.14 of their size apart, as on the site.
  defp layer(words, weight, size, color, opts \\ []) do
    {face, file} = font(weight)
    spacing = if weight == :mono, do: ~s| letter_spacing="#{round(size * 0.14 * 1024)}"|, else: ""

    {layer, _flags} =
      Operation.text!(
        ~s|<span foreground="#{color}"#{spacing}>#{escape(words)}</span>|,
        [font: "#{face} #{size}", fontfile: file, rgba: true, dpi: 72] ++ opts
      )

    layer
  end

  defp font(:regular), do: {"Geist", share_file("Geist-Regular.ttf")}
  defp font(:mono), do: {"Geist Mono", share_file("GeistMono-Regular.ttf")}
  defp font(:pixel), do: {"Geist Pixel Square", share_file("GeistPixel-Square.ttf")}

  defp share_file(name), do: Application.app_dir(:techtree, ["priv", "share_card", name])

  defp escape(words), do: words |> Phoenix.HTML.html_escape() |> Phoenix.HTML.safe_to_string()

  # A Climb's name on one line, without control characters.
  defp plain(words) do
    words
    |> String.replace(~r/[\p{Cc}\p{Cf}]/u, "")
    |> String.replace(~r/\s+/u, " ")
    |> String.trim()
  end

  defp tasks(1), do: "1 task"
  defp tasks(count), do: "#{count} tasks"
end
