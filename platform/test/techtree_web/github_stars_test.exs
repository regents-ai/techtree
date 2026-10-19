defmodule TechtreeWeb.GithubStarsTest do
  @moduledoc """
  The header's star count comes from the server: read by one process however
  many pages ask, kept when a later read fails, and never waited on by a page.
  """

  use TechtreeWeb.ConnCase, async: false
  use ExUnitProperties

  alias TechtreeWeb.GithubStars
  alias TechtreeWeb.GithubStars.Reader

  @counted "regents-ai/techtree on GitHub, 1234 stars"
  @uncounted "Star on GitHub"

  # Every other test reaches nowhere for GitHub and shows no count; these answer
  # for GitHub themselves, through the reader.
  setup do
    GithubStars.delete_all()
    config = Application.fetch_env!(:techtree, :github_stars)

    Application.put_env(
      :techtree,
      :github_stars,
      Keyword.put(config, :req_options, plug: {Req.Test, GithubStars})
    )

    Req.Test.verify_on_exit!()

    # A read still running finishes before the next test, and nothing it kept
    # is seen after these tests.
    on_exit(fn ->
      settled()
      Application.put_env(:techtree, :github_stars, config)
      GithubStars.delete_all()
    end)

    :ok
  end

  defp answer(status, body) do
    Req.Test.expect(GithubStars, fn conn ->
      conn |> Plug.Conn.put_status(status) |> Req.Test.json(body)
    end)

    reader_reads_here()
  end

  # GitHub, as this test answers for it, is what the reader reaches.
  defp reader_reads_here, do: :ok = Req.Test.allow(GithubStars, self(), Process.whereis(Reader))

  # The reader has handled every ask sent before this.
  defp settled, do: :sys.get_state(Reader)

  # The header's GitHub link, found by its accessible name.
  defp github_link(path, name) do
    build_conn()
    |> get(path)
    |> html_response(200)
    |> LazyHTML.from_document()
    |> LazyHTML.query(~s|a[aria-label="#{name}"]|)
  end

  test "the header shows the count GitHub gave, read once for many pages" do
    answer(200, %{"stargazers_count" => 1_234})
    GithubStars.count()
    settled()

    for path <- [~p"/", ~p"/docs", ~p"/start"] do
      assert github_link(path, @counted) |> LazyHTML.text() =~ "1.2k"
    end
  end

  test "before any read has worked, the link stays and shows no count" do
    answer(503, %{"message" => "unavailable"})
    GithubStars.count()
    settled()

    link = github_link(~p"/docs", @uncounted)

    assert Enum.count(link) == 1
    refute LazyHTML.text(link) =~ ~r/\d/
  end

  test "a failed read keeps the last count" do
    answer(200, %{"stargazers_count" => 1_234})
    GithubStars.count()
    settled()

    # The hour is up and GitHub stops answering.
    GithubStars.delete(:fresh)
    answer(503, %{"message" => "unavailable"})
    GithubStars.count()
    settled()

    assert github_link(~p"/docs", @counted) |> LazyHTML.text() =~ "1.2k"
  end

  test "many pages at once, with nothing kept, make exactly one read" do
    reads = :counters.new(1, [])

    Req.Test.stub(GithubStars, fn conn ->
      :counters.add(reads, 1, 1)
      Process.sleep(200)
      Req.Test.json(conn, %{"stargazers_count" => 1_234})
    end)

    reader_reads_here()

    1..50
    |> Task.async_stream(fn _page -> build_conn() |> get(~p"/docs") |> html_response(200) end,
      max_concurrency: 50
    )
    |> Stream.run()

    settled()

    assert :counters.get(reads, 1) == 1
    assert github_link(~p"/docs", @counted) |> Enum.count() == 1
  end

  test "a page with no count kept is drawn at once, without one, while GitHub is slow" do
    Req.Test.stub(GithubStars, fn conn ->
      Process.sleep(2_000)
      Req.Test.json(conn, %{"stargazers_count" => 1_234})
    end)

    reader_reads_here()

    {elapsed, link} = :timer.tc(fn -> github_link(~p"/docs", @uncounted) end)

    assert Enum.count(link) == 1
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
