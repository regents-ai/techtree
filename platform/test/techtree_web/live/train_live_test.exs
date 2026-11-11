defmodule TechtreeWeb.TrainLiveTest do
  @moduledoc """
  The Train pages, drawn from the test folder's two reports: the newest leads
  the list and every comparison opens its own page, one comparison links its
  two files and lists every task, and a name with no report, or a refused
  report, is a 404. The empty and refused cases put a folder of the test's
  own in place of the configured one, so these tests are not run alongside
  each other.
  """

  use TechtreeWeb.ConnCase, async: false

  import ExUnit.CaptureLog
  import Phoenix.LiveViewTest

  alias Techtree.Train.Comparisons
  alias Techtree.TrainFixture

  test "the newest comparison leads, and every comparison opens its own page", %{conn: conn} do
    {:ok, view, _html} = live(conn, ~p"/train")

    assert has_element?(view, ~s|#train-lead a[href="/train/nemotron-lightning-rl"]|)
    refute has_element?(view, "#train-empty")

    for slug <- ["nemotron-lightning-rl", "nemotron-nano-skill"] do
      assert has_element?(view, ~s|#comparison-#{slug} a[href="/train/#{slug}"]|)
    end

    assert has_element?(view, ~s|#private a[href="#{TechtreeWeb.TrainCopy.private_mailto()}"]|)
  end

  test "one comparison links its report and traces and lists every task", %{conn: conn} do
    {:ok, comparison} = Comparisons.fetch("nemotron-nano-skill")
    {:ok, view, _html} = live(conn, ~p"/train/nemotron-nano-skill")

    assert has_element?(view, ~s|a[href="/train/nemotron-nano-skill/report.json"]|)
    assert has_element?(view, ~s|a[href="/train/nemotron-nano-skill/traces.jsonl"]|)
    assert has_element?(view, "#settings")

    for task <- comparison.tasks do
      assert has_element?(view, "#task-#{task.id}")
    end

    assert view |> element(".train-strip") |> render() |> String.split("train-strip__task--") |> length() ==
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

    test "with no reports, the page says there are none yet", %{conn: conn} do
      {:ok, view, _html} = live(conn, ~p"/train")

      assert has_element?(view, "#train-empty[role=status]")
      refute has_element?(view, "#train-lead")
      assert has_element?(view, "#private")
    end

    test "a refused report is not shown and its page is a 404", %{conn: conn, tmp_dir: folder} do
      TrainFixture.write!(folder, "shown")
      TrainFixture.write!(folder, "refused")
      File.write!(Path.join(folder, "refused.traces.jsonl"), "{}\n", [:append])

      capture_log(fn ->
        {:ok, view, _html} = live(conn, ~p"/train")
        assert has_element?(view, ~s|#train-lead a[href="/train/shown"]|)
        refute has_element?(view, ~s|a[href="/train/refused"]|)

        assert_error_sent 404, fn -> live(conn, ~p"/train/refused") end
      end)
    end
  end
end
