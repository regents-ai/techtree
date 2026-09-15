defmodule TechtreeWeb.SafetyEvidenceController do
  @moduledoc """
  One comparison as a file: the run, the pack it ran on with every label, and
  every verdict. Everything the results page shows, and nothing it does not.
  """

  use TechtreeWeb, :controller

  alias Techtree.Safety
  alias Techtree.Safety.TestPack

  def show(conn, %{"id" => id}) do
    case Safety.fetch_run(id) do
      {:ok, run} ->
        {:ok, pack} = TestPack.fetch(run.test_slug)

        conn
        |> put_resp_header(
          "content-disposition",
          ~s(attachment; filename="safety-run-#{run.id}.json")
        )
        |> json(evidence(run, pack))

      :error ->
        conn
        |> put_status(:not_found)
        |> json(%{error: "no comparison is recorded at that address"})
    end
  end

  defp evidence(run, pack) do
    %{
      run: %{
        id: run.id,
        status: run.status,
        test: pack.slug,
        test_version: run.test_version,
        monitor_a: run.monitor_a,
        monitor_b: run.monitor_b,
        model: run.model,
        started_at: run.inserted_at,
        finished_at: run.finished_at,
        failure: run.failure
      },
      policy: pack.policy,
      cases:
        Enum.map(pack.cases, fn recorded ->
          %{
            id: recorded.id,
            title: recorded.title,
            task: recorded.task,
            outcome: recorded.outcome,
            record: recorded.record,
            evidence_event: recorded.evidence_event,
            events: recorded.events
          }
        end),
      verdicts: run.verdicts
    }
  end
end
