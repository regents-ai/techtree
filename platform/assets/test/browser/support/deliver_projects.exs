# Three projects the team delivers to the signed-in visitor of sign_in.exs, one
# for each verdict, and one more package written to a file under tmp/ for the
# team to upload; prints each project's id by verdict and the file's path.
# Run from platform/ with the browser test server's environment.
unless Mix.env() == :test and
         String.starts_with?(System.get_env("MIX_TEST_PARTITION", ""), "browser"),
       do: raise("browser test database only")

Logger.configure(level: :warning)
{:ok, _} = Application.ensure_all_started([:postgrex, :ecto_sql, :ash, :ash_postgres])
{:ok, _} = Techtree.Repo.start_link()

alias Techtree.ProjectPackage

# The browser tests' person is one of the team (config/test.exs).
person = "did:privy:browser-test"
admin = %RegentAgents.Person{privy_user_id: person, role: :admin}

cases = fn rows ->
  Enum.map(rows, fn {id, original, selected} ->
    %{"id" => id, "original_solved" => original, "selected_solved" => selected, "repeats" => 3}
  end)
end

candidate = fn name, solved, attempts, refused, selected ->
  %{
    "candidate" => name,
    "solved" => solved,
    "attempts" => attempts,
    "refused" => refused,
    "selected" => selected
  }
end

# The final test's figures, each consistent with its cases.
verdicts = %{
  "improved" => & &1,
  "inconclusive" => fn manifest ->
    manifest
    |> Map.merge(%{
      "title" => "Invoice triage",
      "success" => "Each invoice reaches the queue that pays it.",
      "verdict" => "inconclusive",
      "cases" =>
        cases.([
          {"invoice-1", 1, 3},
          {"invoice-2", 2, 3},
          {"invoice-3", 3, 2},
          {"invoice-4", 1, 1},
          {"invoice-5", 2, 2},
          {"invoice-6", 1, 1}
        ]),
      "selection" => [
        candidate.("original", 10, 18, false, false),
        candidate.("rewrite", 13, 18, true, false),
        candidate.("skillopt", 12, 18, false, true)
      ]
    })
    |> Map.update!("summary", fn summary ->
      Map.merge(summary, %{
        "final_cases" => 6,
        "original" => %{"solved" => 10, "attempts" => 18},
        "selected" => %{"candidate" => "skillopt", "solved" => 12, "attempts" => 18},
        "difference" => 2,
        "p_value" => 0.31,
        "pass_bar" => 0.8,
        "pass_bar_met" => false,
        "regressions" => 1
      })
    end)
    |> put_in(["setup", "split", "final"], 6)
  end,
  "not_improved" => fn manifest ->
    manifest
    |> Map.merge(%{
      "title" => "Contract clause review",
      "success" => "Each clause that needs a lawyer is flagged.",
      "verdict" => "not_improved",
      "cases" =>
        cases.([{"clause-1", 3, 2}, {"clause-2", 2, 1}, {"clause-3", 2, 3}, {"clause-4", 1, 1}]),
      "selection" => [
        candidate.("original", 8, 12, false, false),
        candidate.("rewrite", 9, 12, false, true),
        candidate.("skillopt", 6, 12, true, false)
      ]
    })
    |> Map.update!("summary", fn summary ->
      Map.merge(summary, %{
        "final_cases" => 4,
        "original" => %{"solved" => 8, "attempts" => 12},
        "selected" => %{"candidate" => "rewrite", "solved" => 7, "attempts" => 12},
        "difference" => -1,
        "p_value" => nil,
        "pass_bar" => 0.75,
        "pass_bar_met" => false,
        "regressions" => 2
      })
    end)
    |> put_in(["setup", "split", "final"], 4)
  end
}

reports = %{
  "improved" => ProjectPackage.files()["report.md"],
  "inconclusive" => """
  # Invoice triage

  The selected Skill solved **12 of 18** final attempts, against 10 of 18 before.
  A difference this size can come from chance, and one case got worse.
  """,
  "not_improved" => """
  # Contract clause review

  The selected Skill solved **7 of 12** final attempts, against 8 of 12 before.
  Two cases got worse, so the original Skill stays.
  """
}

ids =
  Map.new(verdicts, fn {verdict, change} ->
    files = Map.put(ProjectPackage.files(), "report.md", reports[verdict])
    package = ProjectPackage.build(files: files, manifest: change)
    {:ok, project} = Techtree.Projects.deliver_project(person, package, actor: admin)
    {verdict, project.id}
  end)

File.mkdir_p!("tmp")
upload = Path.expand("tmp/#{System.get_env("MIX_TEST_PARTITION")}-#{Ecto.UUID.generate()}.tar.gz")
File.write!(upload, ProjectPackage.build(manifest: &Map.put(&1, "title", "Ticket tagging")))

IO.puts(Jason.encode!(Map.merge(ids, %{"upload" => upload, "upload_title" => "Ticket tagging"})))
