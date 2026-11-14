defmodule TechtreeWeb.TrainLiveTest do
  @moduledoc """
  The comparisons, drawn from the committed folder: Results lists them and each
  opens its own page, which links the Skill, its report and how to check it,
  draws each version's share of attempts as its bar, and lists every case; a
  name with no comparison is a 404. The empty case puts a folder of the test's
  own in place of the configured one, so these tests are not run alongside
  each other.
  """

  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.Train.Comparisons
  alias TechtreeWeb.TrainCopy

  test "Results lists every comparison, each opening its own page", %{conn: conn} do
    {:ok, _view, html} = live(conn, ~p"/results")

    links =
      for item <- html |> LazyHTML.from_document() |> LazyHTML.query("#comparisons li") do
        item |> LazyHTML.query("a") |> LazyHTML.attribute("href") |> List.first()
      end

    assert links == Enum.map(Comparisons.list(), &"/train/#{&1.slug}")
  end

  test "one comparison links its Skill, its report and how to check it, and lists every case",
       %{conn: conn} do
    for comparison <- Comparisons.list() do
      {:ok, view, _html} = live(conn, ~p"/train/#{comparison.slug}")

      assert has_element?(view, ~s|.back-link a[href="/results"]|)
      assert has_element?(view, ~s|a[href="#{comparison.skill.github_url}"]|)
      assert has_element?(view, ~s|a[href="#{comparison.skill.skills_sh_url}"]|)
      assert has_element?(view, ~s|a[href="/train/#{comparison.slug}/report.json"]|)
      assert has_element?(view, ~s|a[href="/docs/verify#blog-section-skill-comparisons"]|)

      for {id, side} <- [original: comparison.final.original, improved: comparison.final.improved] do
        bar = view |> element("#result-#{id}") |> render()
        assert bar =~ "inline-size: #{side.solved * 100 / side.attempts}%"
        assert bar =~ TrainCopy.count(side)
      end

      for item <- comparison.cases do
        assert has_element?(view, ~s|#case-#{item.id}[data-change="#{item.change}"]|)
      end
    end
  end

  test "a name with no comparison is a 404", %{conn: conn} do
    [comparison | _] = Comparisons.list()

    assert_error_sent 404, fn -> live(conn, ~p"/train/missing") end
    assert_error_sent 404, fn -> live(conn, "/train/..%2F#{comparison.slug}") end
  end

  describe "a folder of the test's own" do
    @describetag :tmp_dir

    setup %{tmp_dir: folder} do
      config = Application.fetch_env!(:techtree, Comparisons)
      Application.put_env(:techtree, Comparisons, Keyword.put(config, :folder, folder))
      on_exit(fn -> Application.put_env(:techtree, Comparisons, config) end)
    end

    test "with no comparisons, Results shows none", %{conn: conn} do
      {:ok, view, _html} = live(conn, ~p"/results")

      refute has_element?(view, "#comparisons")
    end
  end
end
