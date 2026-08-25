defmodule TechtreeWeb.SkillController do
  @moduledoc """
  Agent-readable installation metadata for the active public release.
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

    Improve a Skill under controlled conditions and produce a checkable local proof.

    ## Install

    ```sh
    #{Enum.join(release.install_argv, " ")}
    ```

    Release digest: `#{release.digest}`  
    Source revision: `#{release.source_revision}`

    ## Start

    ```sh
    techtree doctor --climb hello-world-climb@1
    techtree climb prepare hello-world-climb@1 --skill path/to/skill
    ```

    Review the preparation output and run the exact one-time `techtree climb start`
    command it prints. Nothing paid starts without approval.

    ## Data boundary

    Techtree does not upload local recordings, result bundles, or submitted Skills.
    The evaluated agent still calls the model provider selected by the campaign.

    Documentation: https://techtree.sh/docs
    """
  end
end
