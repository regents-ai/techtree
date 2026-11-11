defmodule TechtreeWeb.TrainControllerTest do
  @moduledoc """
  The Train comparisons for agents: `/train.json` lists the test folder's two
  reports newest first, each download is the committed file byte for byte
  under its own digest, and both pages answer Markdown at their own address.
  """

  use TechtreeWeb.ConnCase, async: true

  alias Techtree.Catalog.Digest
  alias Techtree.Train.Comparisons

  defp committed(slug, extension), do: File.read!(Path.join(Comparisons.folder(), slug <> extension))

  test "/train.json lists every comparison, newest first, with its addresses", %{conn: conn} do
    conn = get(conn, ~p"/train.json")

    assert get_resp_header(conn, "cache-control") == ["public, max-age=300"]
    assert [rl, skill] = json_response(conn, 200)["comparisons"]

    assert %{
             "slug" => "nemotron-lightning-rl",
             "change" => "rl",
             "arms" => [
               %{"name" => "baseline", "change" => "none", "adapter" => nil},
               %{"name" => "trained", "change" => "rl", "skill_digest" => nil, "adapter" => "techtree/" <> _}
             ]
           } = rl

    assert %{
             "slug" => "nemotron-nano-skill",
             "change" => "skill",
             "outcome" => "uplift",
             "paired" => %{"wins" => 30, "ties" => 28, "losses" => 6, "ci95" => [low, high]},
             "arms" => [%{"name" => "baseline"}, %{"name" => "skill", "skill_digest" => "sha256:" <> _}]
           } = skill

    assert low < high
    assert skill["url"] == url(~p"/train/nemotron-nano-skill")
    assert skill["report_url"] == url(~p"/train/nemotron-nano-skill/report.json")
    assert skill["traces_url"] == url(~p"/train/nemotron-nano-skill/traces.jsonl")
    assert skill["digest"] == Jason.decode!(committed("nemotron-nano-skill", ".json"))["digest"]
  end

  for {file, extension, media_type} <- [
        {"report.json", ".json", "application/json"},
        {"traces.jsonl", ".traces.jsonl", "application/x-ndjson"}
      ] do
    test "the #{file} download is the committed file under its own digest", %{conn: conn} do
      bytes = committed("nemotron-nano-skill", unquote(extension))
      etag = ~s("#{Digest.hash_bytes(bytes)}")

      download = get(conn, "/train/nemotron-nano-skill/#{unquote(file)}")

      assert response(download, 200) == bytes
      assert [content_type] = get_resp_header(download, "content-type")
      assert content_type =~ unquote(media_type)
      assert get_resp_header(download, "etag") == [etag]
      assert get_resp_header(download, "x-content-type-options") == ["nosniff"]

      held =
        build_conn()
        |> put_req_header("if-none-match", etag)
        |> get("/train/nemotron-nano-skill/#{unquote(file)}")

      assert held.status == 304
      assert held.resp_body == ""
    end
  end

  test "a download of a comparison there is none of is a 404 that says where they are listed",
       %{conn: conn} do
    for path <- ["/train/missing/report.json", "/train/missing/traces.jsonl"] do
      assert %{"error" => %{"code" => "comparison_not_found", "hint" => hint}} =
               conn |> get(path) |> json_response(404)

      assert hint =~ "/train.json"
    end
  end

  test "both pages answer Markdown that links each comparison's page and files", %{conn: conn} do
    index = conn |> put_req_header("accept", "text/markdown") |> get(~p"/train") |> response(200)

    for slug <- ["nemotron-lightning-rl", "nemotron-nano-skill"] do
      assert index =~ url(~p"/train/#{slug}")
      assert index =~ url(~p"/train/#{slug}/report.json")
    end

    show =
      build_conn()
      |> put_req_header("accept", "text/markdown")
      |> get(~p"/train/nemotron-nano-skill")
      |> response(200)

    {:ok, comparison} = Comparisons.fetch("nemotron-nano-skill")
    assert show =~ comparison.digest
    assert show =~ comparison.traces_digest
    assert Enum.all?(comparison.tasks, &(show =~ "`#{&1.id}`"))
  end

  test "Markdown for a comparison there is none of is a 404", %{conn: conn} do
    assert_error_sent 404, fn ->
      conn |> put_req_header("accept", "text/markdown") |> get("/train/missing")
    end
  end
end
