defmodule TechtreeWeb.FormalLiveTest do
  @moduledoc """
  Techtree Formal's page and its Markdown list the same advances, each with its
  source, link to the same worked example and start the same email, so neither
  can say something the other doesn't.
  """

  use TechtreeWeb.ConnCase, async: true

  import Phoenix.LiveViewTest

  alias TechtreeWeb.FormalLive

  defp sources(text), do: Regex.scan(~r{https://[^\s")<]+}, text) |> List.flatten()

  test "the page and its Markdown name the same advances, example and email", %{conn: conn} do
    {:ok, _live, html} = live(conn, ~p"/formal")
    page = html |> Floki.parse_document!() |> Floki.attribute("a", "href")

    markdown =
      conn |> put_req_header("accept", "text/markdown") |> get(~p"/formal") |> response(200)

    advances = sources(FormalLive.frontier_markdown())
    assert length(advances) == length(Enum.uniq(advances))
    assert advances != []

    for address <- advances ++ [FormalLive.example_url(), FormalLive.mailto()] do
      assert address in page, address
      assert markdown =~ address, address
    end

    refute markdown =~ "{{"
  end
end
