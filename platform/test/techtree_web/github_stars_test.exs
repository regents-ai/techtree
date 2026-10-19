defmodule TechtreeWeb.GithubStarsTest do
  @moduledoc """
  The header's star count comes from the server, read once and kept, and a page
  without a count still draws its GitHub link.
  """

  use TechtreeWeb.ConnCase, async: false
  use ExUnitProperties

  alias TechtreeWeb.GithubStars

  # Every other test reaches nowhere for GitHub and shows no count; these answer
  # for GitHub themselves.
  setup do
    GithubStars.delete_all()
    config = Application.fetch_env!(:techtree, :github_stars)

    Application.put_env(
      :techtree,
      :github_stars,
      Keyword.put(config, :req_options, plug: {Req.Test, GithubStars})
    )

    # The count these tests read is kept on this machine, and a read started
    # beside a page may still be running; nothing after them sees either.
    on_exit(fn ->
      reads = TechtreeWeb.GithubStars.Reads
      for pid <- Task.Supervisor.children(reads), do: Task.Supervisor.terminate_child(reads, pid)
      Application.put_env(:techtree, :github_stars, config)
      GithubStars.delete_all()
    end)

    :ok
  end

  defp answer(status, body) do
    Req.Test.expect(GithubStars, fn conn ->
      conn |> Plug.Conn.put_status(status) |> Req.Test.json(body)
    end)
  end

  defp header(conn, path), do: conn |> get(path) |> html_response(200) |> LazyHTML.from_document()

  test "the header shows the count GitHub gave, read once for many pages", %{conn: conn} do
    answer(200, %{"stargazers_count" => 1_234})
    GithubStars.refresh()

    for path <- [~p"/", ~p"/docs"] do
      document = header(conn, path)

      assert document |> LazyHTML.query(".masthead__github-count") |> LazyHTML.text() =~ "1.2k"

      assert document |> LazyHTML.query(".masthead__github") |> LazyHTML.attribute("aria-label") ==
               ["regents-ai/techtree on GitHub, 1234 stars"]
    end
  end

  test "when GitHub doesn't answer, the link stays and shows no count", %{conn: conn} do
    answer(503, %{"message" => "unavailable"})
    GithubStars.refresh()

    document = header(conn, ~p"/docs")

    assert document |> LazyHTML.query(".masthead__github") |> Enum.count() == 1
    assert document |> LazyHTML.query(".masthead__github-count") |> Enum.count() == 0
  end

  test "a page with no count kept is drawn at once, without one, while GitHub is slow" do
    # The read beside the page runs in its own process, so the answer is shared.
    Req.Test.set_req_test_to_shared()

    Req.Test.stub(GithubStars, fn conn ->
      Process.sleep(2_000)
      Req.Test.json(conn, %{"stargazers_count" => 5})
    end)

    {elapsed, document} = :timer.tc(fn -> header(build_conn(), ~p"/docs") end)

    assert document |> LazyHTML.query(".masthead__github-count") |> Enum.count() == 0
    assert elapsed < 1_000_000
  end

  property "a compact count reads back as the count, to the nearest tenth of its unit" do
    check all(count <- integer(0..50_000_000)) do
      {figure, unit} = Float.parse(GithubStars.compact(count))
      scale = %{"" => 1, "k" => 1_000, "m" => 1_000_000}

      assert Map.has_key?(scale, unit)
      assert_in_delta figure * scale[unit], count, scale[unit] / 20
    end
  end
end
