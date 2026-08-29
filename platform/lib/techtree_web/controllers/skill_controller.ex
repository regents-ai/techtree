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
      %{installable?: true, introductory_reference: reference} = release
      when is_binary(reference) ->
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

    Improve one declared Skill under fixed conditions, and produce a comparison the
    participant can check offline.

    ## Install

    ```sh
    #{Enum.join(release.install_argv, " ")}
    ```

    #{ReleaseInfo.compatibility(release)}

    Release fingerprint: `#{release.digest}`
    Source revision: `#{release.source_revision}`

    ## First run

    ```sh
    techtree doctor --climb #{release.introductory_reference}
    techtree climb prepare #{release.introductory_reference} --skill path/to/skill
    ```

    Read the preparation output and run the exact one-time `techtree climb start`
    command it prints. Nothing causing LLM token spend starts on its own.

    ## Data boundary

    Techtree uploads nothing unless you publish a finished run yourself. Publishing uploads
    the complete proof bundle — its manifests, signed report and receipts, cited documents,
    and any optional execution record — while Episodes and Traces remain local. The network
    returns a separate signed publication receipt acknowledging acceptance; it is not the
    uploaded proof bundle.
    The agent under test still makes model calls, and those go to the model provider
    the Climb names, under that provider's policies. No Techtree account exists.

    Documentation: https://techtree.sh/docs
    """
  end
end
