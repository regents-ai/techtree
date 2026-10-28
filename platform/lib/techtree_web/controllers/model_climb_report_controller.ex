defmodule TechtreeWeb.ModelClimbReportController do
  @moduledoc """
  A paired agent sends its person's Model Climb proofs and reads them back
  (contract `docs/spec/model-climb-v1.md`, sections 3.5 and 4.1). Every report
  is private to the person whose agent sent it.
  """

  use TechtreeWeb, :controller

  alias Techtree.ModelClimb

  @answer_version "techtree.model-climb.operation.v1alpha1"

  def create(conn, params) do
    actor = conn.assigns.actor

    case get_req_header(conn, "idempotency-key") do
      [key] when byte_size(key) in 1..255 ->
        params
        |> ModelClimb.submit_report(key, actor: actor)
        |> answer_submit(conn)

      _other ->
        refuse(
          conn,
          400,
          :validation_error,
          "Send one Idempotency-Key header of 1 to 255 characters.",
          "Use the proof's digest as the key, and the same key when you retry."
        )
    end
  end

  def index(conn, _params) do
    reports = ModelClimb.list_my_reports!(actor: conn.assigns.actor)

    answer(conn, 200, "model_climb_reports", %{reports: Enum.map(reports, &summary/1)}, [])
  end

  def show(conn, %{"digest" => digest}) do
    case ModelClimb.get_my_report(digest, actor: conn.assigns.actor) do
      {:ok, %{} = report} ->
        answer(
          conn,
          200,
          "model_climb_report",
          %{report: Map.put(summary(report), :proof, Jason.Fragment.new(report.proof))},
          []
        )

      {:ok, nil} ->
        refuse(
          conn,
          404,
          :not_found,
          "No report with that digest is yours.",
          "`regents techtree model-climb reports` lists your reports."
        )
    end
  end

  defp answer_submit({:ok, report}, conn) do
    answer(conn, 200, "model_climb_report_submit", %{report: summary(report)}, [
      %{
        operation_id: "model_climb_report",
        path: "/api/model-climb/v1/reports/#{report.report_digest}"
      }
    ])
  end

  defp answer_submit({:error, error}, conn) do
    case Ash.Error.to_error_class(error) do
      %Ash.Error.Invalid{errors: errors} ->
        case Enum.find(errors, &(Map.get(&1, :field) in [:proof, :idempotency_key])) do
          %{field: :idempotency_key} ->
            refuse(
              conn,
              409,
              :idempotency_conflict,
              "This Idempotency-Key was already used for a different proof.",
              "Send this proof with its own key; resend the first proof with this one."
            )

          %{field: :proof, message: message, vars: vars} ->
            refuse(
              conn,
              400,
              :validation_error,
              message,
              "`regents techtree proof verify` runs every check on your machine; fix the one named and send again.",
              %{check: Keyword.get(vars, :check)}
            )

          _other ->
            refuse(
              conn,
              400,
              :validation_error,
              "The proof could not be read.",
              "Send the proof document of contract 3.5 as the JSON body."
            )
        end

      _other ->
        refuse(
          conn,
          503,
          :unavailable,
          "The report could not be kept.",
          "Send the same request again with the same Idempotency-Key."
        )
    end
  end

  defp summary(report) do
    %{
      report_digest: report.report_digest,
      signer_key_id: report.signer_key_id,
      results: report.results,
      paired_outcomes: report.paired_outcomes,
      received_at: report.inserted_at
    }
  end

  defp answer(conn, status, operation_id, fields, next_actions) do
    conn
    |> put_resp_header("cache-control", "no-store")
    |> put_status(status)
    |> json(
      Map.merge(fields, %{
        schema_version: @answer_version,
        operation_id: operation_id,
        next_actions: next_actions
      })
    )
  end

  defp refuse(conn, status, code, message, hint, details \\ nil) do
    error = %{code: code, message: message, hint: hint}
    error = if details, do: Map.put(error, :details, details), else: error

    conn
    |> put_resp_header("cache-control", "no-store")
    |> put_status(status)
    |> json(%{error: error})
  end
end
