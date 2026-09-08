defmodule TechtreeWeb.PrismLiveTest do
  use TechtreeWeb.ConnCase, async: true

  import Phoenix.LiveViewTest

  test "the development VGPU comparison is a bounded static figure", %{conn: conn} do
    {:ok, live, html} = live(conn, ~p"/prism")
    text = visible_text(html)

    assert text =~ "The WebGPU library, designed for agents."
    assert text =~ "Prompt · CLI · Skill · MCP"
    assert text =~ "Setup vgpu on my project, run npx vgpu"

    assert has_element?(
             live,
             ~s|#prism-demo[data-prism-demo] .rg-technical-figure svg#prism-demo-canvas|
           )

    assert has_element?(live, "#prism-demo [data-triangle-container]")

    refute html =~ ~s|class="masthead"|
    refute has_element?(live, ".colophon")
    refute text =~ "Improve a Skill."
  end
end
