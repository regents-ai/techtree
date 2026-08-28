defmodule TechtreeWeb.PrismLiveTest do
  use TechtreeWeb.ConnCase, async: true

  import Phoenix.LiveViewTest

  test "the public VGPU comparison is a full-bleed prism route", %{conn: conn} do
    {:ok, live, html} = live(conn, ~p"/prism")
    text = visible_text(html)

    assert text =~ "The WebGPU library, designed for agents."
    assert text =~ "Prompt · CLI · Skill · MCP"
    assert text =~ "Setup vgpu on my project, run npx vgpu"

    assert has_element?(
             live,
             ~s|#prism-demo[phx-hook="Optics"][phx-update="ignore"][data-prism-demo][data-optics-kind="prism"][data-optics-module][data-optics-source="/vendor/vgpu-prism/prism-current.js"] canvas[data-optics-canvas]|
           )

    assert has_element?(live, "#prism-demo [data-triangle-container]")

    refute html =~ ~s|class="masthead"|
    refute has_element?(live, ".colophon")
    refute text =~ "Improve a Skill."
  end
end
