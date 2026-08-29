defmodule TechtreeWeb.StartLiveTest do
  use TechtreeWeb.ConnCase, async: true

  import Phoenix.LiveViewTest

  @instruction "Set up Techtree and run the Hello World Climb."

  test "Start presents one copyable setup instruction", %{conn: conn} do
    {:ok, live, html} = live(conn, ~p"/start")

    assert visible_text(html) =~ @instruction

    assert has_element?(
             live,
             ~s|#copy-setup-instruction[data-copy-value="#{@instruction}"]|,
             "Copy"
           )

    refute html =~ "My agent is installing"
    refute html =~ "I’m installing"
    refute html =~ "hermes plugins install"
    refute html =~ "uv tool install"
  end

  test "query parameters do not create alternate installation paths", %{conn: conn} do
    {:ok, _live, html} = live(conn, ~p"/start?install=me")

    assert visible_text(html) =~ @instruction
    refute html =~ "Prefer installing it yourself?"
  end
end
