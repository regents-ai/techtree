defmodule TechtreeWeb.ErrorHTMLTest do
  use TechtreeWeb.ConnCase, async: true

  # Bring render_to_string/4 for testing custom views
  import Phoenix.Template, only: [render_to_string: 4]

  test "renders 404.html" do
    html = render_to_string(TechtreeWeb.ErrorHTML, "404", "html", [])

    assert html =~ "We can’t find that page"
    assert html =~ ~s|href="/"|
    assert html =~ ~s|href="/results"|

    dark =
      render_to_string(TechtreeWeb.ErrorHTML, "404", "html",
        conn: build_conn() |> put_req_header("cookie", "techtree_theme=dark")
      )

    assert dark =~ ~s(data-theme="dark")
  end

  test "renders 500.html" do
    html = render_to_string(TechtreeWeb.ErrorHTML, "500", "html", [])

    assert html =~ "Something went wrong"
    assert html =~ ~s|href="/"|
  end

  test "falls back to the standard status text for other errors" do
    assert render_to_string(TechtreeWeb.ErrorHTML, "400", "html", []) == "Bad Request"

    assert render_to_string(TechtreeWeb.ErrorHTML, "413", "html", []) ==
             "Request Entity Too Large"
  end
end
