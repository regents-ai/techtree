defmodule TechtreeWeb.TrainControllerTest do
  @moduledoc """
  The comparisons for agents: `/train.json` lists the committed comparisons
  newest first with their figures and addresses, the report download is the
  committed file byte for byte under its own digest, and Results and each
  comparison answer Markdown at their own address.
  """

  use TechtreeWeb.ConnCase, async: true

  alias Techtree.Catalog.Digest
  alias Techtree.Train.Comparisons

  defp committed(slug), do: File.read!(Path.join(Comparisons.folder(), slug <> ".json"))

  test "/train.json lists every comparison, newest first, with its figures and addresses",
       %{conn: conn} do
    conn = get(conn, ~p"/train.json")

    assert get_resp_header(conn, "cache-control") == ["public, max-age=300"]
    listed = json_response(conn, 200)["comparisons"]
    comparisons = Comparisons.list()

    assert Enum.map(listed, & &1["slug"]) == Enum.map(comparisons, & &1.slug)

    for {entry, comparison} <- Enum.zip(listed, comparisons) do
      %{final: %{original: original, improved: improved}, changes: changes} = comparison

      assert %{
               "url" => url,
               "report_url" => report_url,
               "date" => date,
               "final" => %{
                 "original" => %{"solved" => original_solved, "attempts" => attempts},
                 "improved" => %{"solved" => improved_solved}
               },
               "changes" => %{"better" => better, "same" => same, "worse" => worse}
             } = entry

      refute Map.has_key?(entry, "cases")
      assert url == url(~p"/train/#{comparison.slug}")
      assert report_url == url(~p"/train/#{comparison.slug}/report.json")
      assert date == Date.to_iso8601(comparison.date)

      assert {original_solved, improved_solved, attempts} ==
               {original.solved, improved.solved, original.attempts}

      assert {better, same, worse} == {changes.better, changes.same, changes.worse}
    end
  end

  test "the report download is the committed file under its own digest", %{conn: conn} do
    for comparison <- Comparisons.list() do
      bytes = committed(comparison.slug)
      etag = ~s("#{Digest.hash_bytes(bytes)}")

      download = get(conn, "/train/#{comparison.slug}/report.json")

      assert response(download, 200) == bytes
      assert [content_type] = get_resp_header(download, "content-type")
      assert content_type =~ "application/json"
      assert get_resp_header(download, "etag") == [etag]
      assert get_resp_header(download, "x-content-type-options") == ["nosniff"]

      held =
        build_conn()
        |> put_req_header("if-none-match", etag)
        |> get("/train/#{comparison.slug}/report.json")

      assert held.status == 304
      assert held.resp_body == ""
    end
  end

  test "a download of a comparison there is none of is a 404 that says where they are listed",
       %{conn: conn} do
    assert %{"error" => %{"code" => "comparison_not_found", "hint" => hint}} =
             conn |> get("/train/missing/report.json") |> json_response(404)

    assert hint =~ "/train.json"
  end

  test "Results and each comparison answer Markdown that links each comparison's page and report",
       %{conn: conn} do
    results =
      conn |> put_req_header("accept", "text/markdown") |> get(~p"/results") |> response(200)

    for comparison <- Comparisons.list() do
      assert results =~ "(/train/#{comparison.slug})"

      show =
        build_conn()
        |> put_req_header("accept", "text/markdown")
        |> get(~p"/train/#{comparison.slug}")
        |> response(200)

      assert show =~ url(~p"/train/#{comparison.slug}/report.json")
      assert show =~ comparison.skill.github_url
      assert show =~ comparison.skill.skills_sh_url
      assert Enum.all?(comparison.cases, &(show =~ "`#{&1.id}`"))
    end
  end

  test "Markdown for a comparison there is none of is a 404", %{conn: conn} do
    assert_error_sent 404, fn ->
      conn |> put_req_header("accept", "text/markdown") |> get("/train/missing")
    end
  end
end
