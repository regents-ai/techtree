defmodule TechtreeWeb.AgentsController do
  @moduledoc """
  The agent guide at `/agents.md`: the installation facts, written for the
  agent rather than the reader, then how a paired agent signs its requests, then
  the Techtree skill's own sections (`TechtreeWeb.SkillController`), word for
  word.

  An agent that lands here should be able to answer three questions without
  guessing: what this is, which exact command installs it, and what happens to
  the work it produces. Every value comes from the release being served, so
  this document cannot describe a version the site is not publishing — and when
  the served coordinates are stand-ins there is nothing to describe, which this
  says plainly rather than handing over a command that installs nothing.
  """

  use TechtreeWeb, :controller

  alias Techtree.Catalog.Query
  alias TechtreeWeb.CampaignFacts
  alias TechtreeWeb.ModelAccess
  alias TechtreeWeb.ReleaseInfo
  alias TechtreeWeb.SkillController

  @access """
  ## Agent access

  Local experiments and offline proof verification stay available without
  pairing. Public catalog, result and key reads need no sign-in.

  For protected work, act as your own named agent. Use the existing signer
  described at https://siwa.regents.sh/skill.md; never use the owner's browser
  cookies or replace a missing signer. Prepare the exact method, path and body
  for audience `techtree`, sign that request, then send its proof. A changed
  request, wrong audience or replayed proof must be refused. Retry a logical
  operation with fresh proof and unchanged publication bytes.

  Start with `agent_whoami` (GET /api/agents/v1/whoami). It needs fresh proof but
  no pairing and awards no Points. If `effective_access.paired` is false, ask the
  owner to sign in at https://regents.sh/account and create an agent pairing
  code. Redeem it with signed POST /api/agents/v1/pair using code, name and
  harness. Codes are private, expire and work once. One owner may pair at most
  100 active agents across Regent sites. Revocation stops protected work;
  re-pairing creates a new episode and restores no previous spending grant.

  Signed account reads require a current pairing and the owner's existing
  canonical account. `account_balances`, `credits_history` and `points_balance`
  prepare existing /tools/account routes. Account IDs or wallets submitted as
  inputs never select an owner. Spending starts disabled and only the owner
  manages grants, pairing controls and account security. Credits permission
  grants no access to wallet funds. Techtree does not activate Points or award
  Points for reads.

  Hosted publication and withdrawal additionally require the participant's
  independent signed proof. The SIWA identity does not replace that key. Both use
  POST /api/v1/publications with the exact original JSON bytes, at most
  2,097,152 bytes, subject to existing rate and proof checks. A receipt retry
  preserves its bundle digest and original receipt. The release above signs these
  requests for you.

  Signed requests through a browser's own tools (`agent_whoami`, the account
  reads and `techtree_publication`) have not yet been tested end to end in a real
  browser; `techtree_publication` passes the original JSON bytes through
  unchanged. Do not claim success from discovery, preparation or an unsigned
  refusal. The profile page remains withdrawn; use Regents' account page for
  owner controls. Human-backed registry attributes are optional and do not grant
  authority.

  On refusal, retain the safe code, time, origin, route, source/released
  versions and any assistance. Follow the returned recovery hint. Never publish
  credentials, pairing codes, private records or fake evaluation results as a
  repair report.

  """

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

    ## Where this runs

    Every command here runs on the person's own computer. A browser or web-only
    agent cannot run them, and nothing it reads on techtree.sh starts a run: give
    the person, or their local agent, this page's address
    (https://techtree.sh/agents.md) and let them follow it there.

    ## Install

    Install this release, not the newest one you know of:

    ```sh
    #{Enum.join(release.install_argv, " ")}
    ```

    #{ReleaseInfo.compatibility(release)}

    Release fingerprint: `#{release.digest}`
    Source revision: `#{release.source_revision}`

    Then check it: `regents --version` prints #{release.version}. Anything else
    is not this release; install this one before going on.

    Run `regents techtree doctor`. It checks what the machine needs without
    calling a model. From there, every answer ends with its next steps: the exact
    command to run next, or what the person has to do first. Follow those; the
    commands below show the shape of each step.

    ## Make the tasks

    1. Ask the person where their Skill is: a folder with a `SKILL.md`.
    2. Run `regents techtree forge inspect-skill PATH`. It reads the files and runs none
       of them. Show the person what it prints. If it refuses the Skill, relay the
       reason and stop.
    3. Ask the person which provider and model should plan the tasks, then run
       `regents techtree forge plan SOURCE_ID --provider PROVIDER --model MODEL`. It calls
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
    tasks at any time (`regents techtree forge verify COLLECTION_ID`) or write a copy to
    share (`regents techtree forge export COLLECTION_ID --to FOLDER`). If a built task is
    wrong, the person can fix a copy of it by hand and record that with
    `regents techtree forge correct-task CONSTRUCTION_ID TASK_NAME DIR`.

    ## Compare, then decide

    6. Ask the person which provider and model should work the tasks, and what
       to compare against: no Skill, or an earlier version of their Skill (a
       folder with its own `SKILL.md`). Both runs use the same provider and model.
    7. Run the baseline:
       `regents techtree forge run --arm baseline --collection COLLECTION_ID --provider PROVIDER --model MODEL`,
       adding `--skill OLD_PATH` only to measure against the earlier version.
       It starts nothing yet. It prints a review of the model calls, tools and
       limits; show it exactly as printed and stop. Only after the person says
       yes to that exact review, run the command Techtree printed next.
    8. Run the candidate the same way, with the Skill being tested:
       `regents techtree forge run --arm candidate --collection COLLECTION_ID --provider PROVIDER --model MODEL --skill PATH`.
       It waits for its own yes.
    9. Run `regents techtree forge compare BASELINE_RUN_ID CANDIDATE_RUN_ID`. It calls no
       model. It pairs every task across the two runs and gives a verdict:
       improved, regressed, mixed, no difference, or inconclusive when too few
       tasks were scored on both sides. It gives a verdict for all the tasks,
       one for the tasks an improving agent may study, and one for the held-out
       tasks. Once a Skill has been revised from these tasks, only the held-out
       verdict can answer "should I keep this change?". Show the person the
       verdicts and where the report was written, and let them decide.

    To revise the Skill once and test the revision, run
    `regents techtree uplift context COMPARISON_ID` for what the comparison may be
    studied from (never the held-out tasks), write the revised Skill into a new
    folder, then run
    `regents techtree uplift prepare --from-run COMPARISON_ID --candidate-skill NEW_PATH`
    and `regents techtree uplift start REVISION_ID`, which waits for its own yes.

    `regents techtree forge status ID` shows where any build, plan, run or comparison
    stands.

    #{climb_section(release)}## Data boundary

    Testing a Skill uploads nothing to Techtree. Planning, building and the two
    runs send the Skill's files and the tasks to the model provider the person
    chose, on their own sign-in, and only after they approve the review that
    says so. Everything else stays in Techtree's folder on their computer until
    they share it. No Techtree account exists.

    #{@access}
    ## Wallet Bench

    To learn which coding agent can set up and use which wallet tool, read
    https://techtree.sh/wallet-bench.md: each pair's newest judged result, then
    every test with a result, each linked to its evidence.

    Documentation: https://techtree.sh/docs

    #{String.trim_trailing(SkillController.shared_sections())}
    """
  end

  defp climb_section(%{introductory_reference: reference}) when is_binary(reference) do
    routes =
      reference
      |> Query.get_climb_by_reference!()
      |> CampaignFacts.trial!()
      |> Map.fetch!(:routes)

    """
    ## The introductory Climb

    This release also carries a toy comparison, `#{reference}`, run with and
    without a starter Skill. It shows how a run works; its tasks say nothing
    about the person's own Skill.

    ```sh
    regents techtree setup
    regents techtree doctor --climb #{reference}
    regents techtree skill starter
    #{prepare_lines(reference, routes)}
    ```

    Each run uses one of these routes. Ask the person which one to use:

    #{Enum.map_join(routes, "\n", &("- " <> ModelAccess.needs!(&1)))}

    Read the preparation output and run the exact one-time `regents techtree climb start`
    command it prints. Nothing causing model token spend starts on its own.
    Publishing a finished Climb run is optional and uploads its proof bundle,
    while Episodes and Traces remain local. Only Climb runs can be published
    today; a Skill comparison stays on the person's computer, and
    `regents techtree forge export` writes a copy to share.

    """
  end

  defp climb_section(_release), do: ""

  # One prepare command for each route the Climb offers, each after a comment
  # naming its route.
  defp prepare_lines(reference, routes) do
    routes
    |> ModelAccess.prepare_lines([
      "regents",
      "techtree",
      "climb",
      "prepare",
      reference,
      "--skill",
      "path/to/skill"
    ])
    |> Enum.map_join("\n", fn
      {:comment, text} -> "# " <> text
      {:command, argv} -> Enum.join(argv, " ")
    end)
  end
end
