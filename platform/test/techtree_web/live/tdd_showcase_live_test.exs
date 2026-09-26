defmodule TechtreeWeb.TddShowcaseLiveTest do
  @moduledoc """
  The example comparison page, drawn from the test folder: the verdict names
  the held-out tasks by how they went, the tasks the improving agent could see
  stand apart, and the commands and the export folder are the export's own.

  A comparison with tasks missing a score is drawn from one of the variant
  records, put in place of the test folder's own; the page reads the
  configured folder, so these tests are not run alongside each other.
  """

  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias TechtreeWeb.TddShowcase

  setup %{conn: conn} do
    {:ok, view, _html} = live_isolated(conn, TechtreeWeb.TddShowcaseLive)
    %{view: view, showcase: TddShowcase.load!(TddShowcase.folder())}
  end

  test "the verdict section lists only held-out tasks, each under how it went", %{
    view: view,
    showcase: showcase
  } do
    for {outcome, tasks} <- TddShowcase.by_outcome(showcase.held_out.tasks), tasks != [] do
      text = view |> element("#held-out-#{outcome}") |> render()
      assert Enum.all?(tasks, &(text =~ &1.name))
    end

    verdict = view |> element("#showcase-assessment") |> render()
    refute Enum.any?(showcase.study.tasks, &(verdict =~ &1.name))
  end

  test "the study tasks are shown apart from the verdict", %{view: view, showcase: showcase} do
    study = view |> element("#showcase-study") |> render()
    assert Enum.all?(showcase.study.tasks, &(study =~ &1.name))
    refute Enum.any?(showcase.held_out.tasks, &(study =~ &1.name))
  end

  test "the rerun commands copy exactly the export README's block", %{view: view} do
    readme = File.read!(Path.join([TddShowcase.folder(), "export", "README.md"]))
    [_, block] = Regex.run(~r/### The commands, in order\n\n```\n(.*?)\n```/s, readme)

    button = view |> element("#copy-showcase-rerun") |> render()
    assert [_, ^block] = Regex.run(~r/data-copy-value="([^"]*)"/, button)
  end

  test "the export folder link is the configured one", %{view: view} do
    assert has_element?(view, ~s|a#showcase-export[href="#{TddShowcase.export_url()}"]|)
  end

  describe "a comparison with held-out tasks missing a score" do
    @describetag :tmp_dir

    setup %{conn: conn, tmp_dir: tmp_dir} do
      folder = Path.join(tmp_dir, "tdd-showcase")
      File.cp_r!(TddShowcase.folder(), folder)

      File.cp!(
        Path.expand(
          "../../support/fixtures/tdd-showcase-variants/too-few/comparison.json",
          __DIR__
        ),
        Path.join(folder, "comparison.json")
      )

      config = Application.fetch_env!(:techtree, TddShowcase)
      Application.put_env(:techtree, TddShowcase, Keyword.put(config, :folder, folder))
      on_exit(fn -> Application.put_env(:techtree, TddShowcase, config) end)

      {:ok, view, _html} = live_isolated(conn, TechtreeWeb.TddShowcaseLive)
      %{view: view, showcase: TddShowcase.load!(folder)}
    end

    test "the verdict names each task missing a score, and which run left it unscored",
         %{view: view, showcase: showcase} do
      assert has_element?(view, "#showcase-assessment.assessment--not_enough_evidence")

      missing = view |> element("#held-out-not_scored") |> render()

      for task <- TddShowcase.by_outcome(showcase.held_out.tasks).not_scored do
        assert missing =~ task.name
        assert has_element?(view, "#task-#{task.name} p", "No score")
      end
    end
  end
end
