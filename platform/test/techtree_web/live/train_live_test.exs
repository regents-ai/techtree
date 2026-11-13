defmodule TechtreeWeb.TrainLiveTest do
  @moduledoc """
  The comparisons, drawn from the test folder's two reports: Results lists
  them newest first and each opens its own page, one comparison links its two
  files, how to check them and every task, and a name with no report, or a
  refused report, is a 404. The empty and refused cases put a folder of the
  test's own in place of the configured one, so these tests are not run
  alongside each other.
  """

  use TechtreeWeb.ConnCase, async: false

  import ExUnit.CaptureLog
  import Phoenix.LiveViewTest

  alias Techtree.Train.Comparisons
  alias Techtree.TrainFixture

  test "Results lists every comparison, newest first, each opening its own page", %{conn: conn} do
    {:ok, _view, html} = live(conn, ~p"/results")

    links =
      for item <- html |> LazyHTML.from_document() |> LazyHTML.query("#comparisons li") do
        item |> LazyHTML.query("a") |> LazyHTML.attribute("href") |> List.first()
      end

    assert links == ["/train/nemotron-lightning-rl", "/train/nemotron-nano-skill"]
  end

  test "one comparison links its report, its traces and how to check them, and lists every task",
       %{conn: conn} do
    {:ok, comparison} = Comparisons.fetch("nemotron-nano-skill")
    {:ok, view, _html} = live(conn, ~p"/train/nemotron-nano-skill")

    assert has_element?(view, ~s|.back-link a[href="/results"]|)
    assert has_element?(view, ~s|a[href="/train/nemotron-nano-skill/report.json"]|)
    assert has_element?(view, ~s|a[href="/train/nemotron-nano-skill/traces.jsonl"]|)
    assert has_element?(view, ~s|a[href="/docs/verify#blog-section-skill-comparisons"]|)
    assert has_element?(view, "#settings")

    for task <- comparison.tasks do
      assert has_element?(view, "#task-#{task.id}")
    end

    assert view
           |> element(".train-strip")
           |> render()
           |> String.split("train-strip__task--")
           |> length() ==
             comparison.environment.task_count + 1
  end

  test "a name with no report is a 404", %{conn: conn} do
    assert_error_sent 404, fn -> live(conn, ~p"/train/missing") end
    assert_error_sent 404, fn -> live(conn, "/train/..%2Fnemotron-nano-skill") end
  end

  describe "a folder of the test's own" do
    @describetag :tmp_dir

    setup %{tmp_dir: folder} do
      config = Application.fetch_env!(:techtree, Comparisons)
      Application.put_env(:techtree, Comparisons, Keyword.put(config, :folder, folder))
      on_exit(fn -> Application.put_env(:techtree, Comparisons, config) end)
    end

    test "with no reports, Results shows no comparisons", %{conn: conn} do
      {:ok, view, _html} = live(conn, ~p"/results")

      refute has_element?(view, "#comparisons")
    end

    test "a refused report is not shown and its page is a 404", %{conn: conn, tmp_dir: folder} do
      TrainFixture.write!(folder, "shown")
      TrainFixture.write!(folder, "refused")
      File.write!(Path.join(folder, "refused.traces.jsonl"), "{}\n", [:append])

      capture_log(fn ->
        {:ok, view, _html} = live(conn, ~p"/results")
        assert has_element?(view, ~s|#comparisons a[href="/train/shown"]|)
        refute has_element?(view, ~s|a[href="/train/refused"]|)

        assert_error_sent 404, fn -> live(conn, ~p"/train/refused") end
      end)
    end
  end
end
