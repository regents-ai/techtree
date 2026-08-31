defmodule TechtreeWeb.ErrorHTMLTest do
  use TechtreeWeb.ConnCase, async: true

  # Bring render_to_string/4 for testing custom views
  import Phoenix.Template, only: [render_to_string: 4]

  test "renders 404.html" do
    html = render_to_string(TechtreeWeb.ErrorHTML, "404", "html", [])

    assert html =~ "This page is not part of Techtree."
    assert html =~ ~s|href="/"|
    assert html =~ ~s|href="/results"|
  end

  test "renders 500.html" do
    html = render_to_string(TechtreeWeb.ErrorHTML, "500", "html", [])

    assert html =~ "Techtree could not load this page."
    assert html =~ ~s|href="/"|
  end

  test "falls back to the standard status text for other errors" do
    assert render_to_string(TechtreeWeb.ErrorHTML, "400", "html", []) == "Bad Request"

    assert render_to_string(TechtreeWeb.ErrorHTML, "413", "html", []) ==
             "Request Entity Too Large"
  end
end
