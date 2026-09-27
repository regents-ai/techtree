defmodule TechtreeWeb.SkillController do
  @moduledoc """
  The same installation facts, written for the agent rather than the reader.

  An agent that lands here should be able to answer three questions without
  guessing: what this is, which exact command installs it, and what happens to
  the work it produces. Every value comes from the release being served, so
  this document cannot describe a version the site is not publishing — and when
  the served coordinates are stand-ins there is nothing to describe, which this
  says plainly rather than handing over a command that installs nothing.
  """

  use TechtreeWeb, :controller

  alias TechtreeWeb.ReleaseInfo

  def show(conn, _params) do
    case ReleaseInfo.current() do
      %{installable?: true} = release ->
        conn
        |> put_resp_content_type("text/markdown", "utf-8")
        |> send_resp(200, document(release))

      _release ->
        conn
        |> put_resp_content_type("text/plain", "utf-8")
        |> send_resp(404, "No concrete Techtree release is active on this channel.\n")
    end
  end

  defp document(release) do
    """
    # Techtree #{release.version}

    Test a person's Skill: make tasks from what it teaches, run their agent on
    them without the Skill (or with an earlier version of it) and with it, and
    compare. Everything runs on their own computer, and every step that calls a
    model waits for the person's yes.

    ## Install

    ```sh
    #{Enum.join(release.install_argv, " ")}
    ```

    #{ReleaseInfo.compatibility(release)}

    Release fingerprint: `#{release.digest}`
    Source revision: `#{release.source_revision}`

    If `techtree --version` already prints #{release.version}, it is installed.

    ## Make the tasks

    1. Ask the person where their Skill is: a folder with a `SKILL.md`.
    2. Run `techtree forge inspect-skill PATH`. It reads the files and runs none
       of them. Show the person what it prints. If it refuses the Skill, relay the
       reason and stop.
    3. Ask the person which provider and model should plan the tasks, then run
       `techtree forge plan SOURCE_ID --provider PROVIDER --model MODEL`. It calls
       no model. It prints a review: what would be sent, to which provider, and
       the limits. Show it exactly as printed. The model call uses the person's
       Hermes profile `techtree`; if that profile is missing or signed out,
       Techtree says how to fix it, and the person does that themselves.
    4. Stop and ask. Only after the person says yes to that exact review, run
       the command Techtree printed next, with `--yes --reviewed-on host-agent`.
    5. Go on the same way. Each command prints the next one, and each review
       waits for the person's own yes: correcting the proposed tasks, building
       them, and accepting the ones that qualified. Never approve anything on
       the person's behalf, and never answer a review for them.

    Accepting prints the collection's ID. The person can check the accepted
    tasks at any time (`techtree forge verify COLLECTION_ID`) or write a copy to
    share (`techtree forge export COLLECTION_ID --to FOLDER`). If a built task is
    wrong, the person can fix a copy of it by hand and record that with
    `techtree forge correct-task CONSTRUCTION_ID TASK_NAME DIR`.

    ## Compare, then decide

    6. Ask the person which provider and model should work the tasks, and what
       to compare against: no Skill, or an earlier version of their Skill (a
       folder with its own `SKILL.md`). Both runs use the same provider and model.
    7. Run the baseline:
       `techtree forge run --arm baseline --collection COLLECTION_ID --provider PROVIDER --model MODEL`,
       adding `--skill OLD_PATH` only to measure against the earlier version.
       It starts nothing yet. It prints a review of the model calls, tools and
       limits; show it exactly as printed and stop. Only after the person says
       yes to that exact review, run the command Techtree printed next.
    8. Run the candidate the same way, with the Skill being tested:
       `techtree forge run --arm candidate --collection COLLECTION_ID --provider PROVIDER --model MODEL --skill PATH`.
       It waits for its own yes.
    9. Run `techtree forge compare BASELINE_RUN_ID CANDIDATE_RUN_ID`. It calls no
       model. It pairs every task across the two runs and gives a verdict:
       improved, regressed, mixed, no difference, or inconclusive when too few
       tasks were scored on both sides. It gives a verdict for all the tasks,
       one for the tasks an improving agent may study, and one for the held-out
       tasks. Once a Skill has been revised from these tasks, only the held-out
       verdict can answer "should I keep this change?". Show the person the
       verdicts and where the report was written, and let them decide.

    To revise the Skill once and test the revision, run
    `techtree uplift context COMPARISON_ID` for what the comparison may be
    studied from (never the held-out tasks), write the revised Skill into a new
    folder, then run
    `techtree uplift prepare --from-run COMPARISON_ID --candidate-skill NEW_PATH`
    and `techtree uplift start REVISION_ID`, which waits for its own yes.

    `techtree forge status ID` shows where any build, plan, run or comparison
    stands.

    #{climb_section(release)}## Data boundary

    Testing a Skill uploads nothing to Techtree. Planning, building and the two
    runs send the Skill's files and the tasks to the model provider the person
    chose, on their own sign-in, and only after they approve the review that
    says so. Everything else stays in Techtree's folder on their computer until
    they share it. No Techtree account exists.

    Documentation: https://techtree.sh/docs
    """
  end

  defp climb_section(%{introductory_reference: reference}) when is_binary(reference) do
    """
    ## The introductory Climb

    This release also carries a toy comparison, `#{reference}`, run with and
    without a starter Skill. It shows how a run works; its tasks say nothing
    about the person's own Skill.

    ```sh
    techtree setup
    techtree doctor --climb #{reference}
    techtree skill starter
    techtree climb prepare #{reference} --skill path/to/skill
    ```

    Read the preparation output and run the exact one-time `techtree climb start`
    command it prints. Nothing causing model token spend starts on its own.
    Publishing a finished Climb run is optional and uploads its proof bundle,
    while Episodes and Traces remain local. Only Climb runs can be published
    today; a Skill comparison stays on the person's computer, and
    `techtree forge export` writes a copy to share.

    """
  end

  defp climb_section(_release), do: ""
end
