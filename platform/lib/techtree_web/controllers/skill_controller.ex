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

    Create an environment from a person's Skill: tasks built from what the Skill
    teaches, checked, and accepted by the person, on their own computer.

    ## Install

    ```sh
    #{Enum.join(release.install_argv, " ")}
    ```

    #{ReleaseInfo.compatibility(release)}

    Release fingerprint: `#{release.digest}`
    Source revision: `#{release.source_revision}`

    If `techtree --version` already prints #{release.version}, it is installed.

    ## Create an environment

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

    Afterwards the person can check the accepted tasks (`techtree forge verify`),
    write a private copy to share (`techtree forge export`), or run them, which
    needs its own approval.

    #{climb_section(release)}## Data boundary

    Creating an environment uploads nothing to Techtree. The planning and
    building steps send the Skill's files to the model provider the person
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
    without a starter Skill:

    ```sh
    techtree setup
    techtree doctor --climb #{reference}
    techtree climb prepare #{reference} --skill path/to/skill
    ```

    Read the preparation output and run the exact one-time `techtree climb start`
    command it prints. Nothing causing model token spend starts on its own.
    Publishing a finished run is optional and uploads its proof bundle, while
    Episodes and Traces remain local.

    """
  end

  defp climb_section(_release), do: ""
end
