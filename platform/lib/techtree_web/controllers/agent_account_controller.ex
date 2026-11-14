defmodule TechtreeWeb.AgentAccountController do
  @moduledoc """
  The current paired agent's reads of its person's account: their Points, and
  the projects Techtree's team delivered to them, as their Projects pages show
  them (`TechtreeWeb.ProjectsLive`), with where to download each package.
  """
  use TechtreeWeb, :controller

  alias RegentPoints.Rules
  alias Techtree.Points.Board
  alias Techtree.{Projects, SharedReading}
  alias TechtreeWeb.{PointsEntries, ProjectPackageController, ProjectsLive, UnexpectedFailure}

  @points_off "Earning Points is off on this site."

  # Points as decimal text, the same figures the Points page shows. While the
  # page would show the board as not read, the whole answer is unavailable.
  def points(conn, _params) do
    actor = conn.assigns.actor

    with {:ok, summary} <- RegentPoints.summary(actor: actor),
         {:ok, %{reading: %{} = board}} <- SharedReading.fetch(Board.key()) do
      earning = Rules.active()
      answer = PointsEntries.answer(summary, board, actor.human_account_id, earning != [])
      private_json(conn, with_note(answer, points_note(earning)))
    else
      {:error, error} -> conn |> UnexpectedFailure.log(error) |> unavailable()
      _board_not_read -> unavailable(conn)
    end
  end

  # The person's projects, newest first.
  def projects(conn, _params) do
    case Projects.list_my_projects(actor: conn.assigns.actor) do
      {:ok, projects} -> private_json(conn, %{projects: Enum.map(projects, &listed/1)})
      {:error, error} -> conn |> UnexpectedFailure.log(error) |> unavailable()
    end
  end

  # One of the person's projects, with all its page shows.
  def project(conn, %{"id" => id}),
    do: own(conn, id, &Projects.get_my_project/2, &private_json(&1, whole(&2)))

  # One of the person's projects' package, as the page's Download sends it.
  def package(conn, %{"id" => id}),
    do: own(conn, id, &Projects.get_my_package/2, &ProjectPackageController.send_package/2)

  defp own(conn, id, read, answer) do
    found =
      case Ecto.UUID.cast(id) do
        {:ok, id} -> read.(id, actor: conn.assigns.actor)
        :error -> {:ok, nil}
      end

    case found do
      {:ok, %{} = project} -> answer.(conn, project)
      {:ok, nil} -> project_not_found(conn)
      {:error, error} -> conn |> UnexpectedFailure.log(error) |> unavailable()
    end
  end

  defp listed(project) do
    %{
      id: project.id,
      title: project.title,
      service: project.line,
      verdict: project.verdict,
      verdict_name: ProjectsLive.verdict_name(project.verdict),
      delivered_at: project.delivered_at,
      url: url(~p"/account/projects/#{project.id}")
    }
  end

  defp whole(project) do
    manifest = project.manifest

    project
    |> listed()
    |> Map.merge(%{
      success: manifest["success"],
      summary: Map.delete(manifest["summary"], "cost_cents"),
      cases: manifest["cases"],
      selection: manifest["selection"],
      setup: manifest["setup"],
      report_md: project.report_md,
      package: %{
        size_bytes: project.package_size,
        sha256: project.package_sha256,
        url: url(~p"/api/v1/account/projects/#{project.id}/package")
      }
    })
  end

  defp project_not_found(conn),
    do:
      TechtreeWeb.ExactResponse.send_error(
        conn,
        404,
        :project_not_found,
        "Your person has no project with that id.",
        "List their projects at #{url(~p"/api/v1/account/projects")}."
      )

  defp points_note([]), do: @points_off
  defp points_note(_earning), do: nil

  defp with_note(answer, nil), do: answer
  defp with_note(answer, note), do: Map.put(answer, :note, note)

  defp private_json(conn, answer),
    do: conn |> put_resp_header("cache-control", "no-store") |> json(answer)

  defp unavailable(conn),
    do:
      TechtreeWeb.ExactResponse.send_error(
        conn,
        503,
        :unavailable,
        "That could not be reached right now.",
        "Try again in a moment."
      )
end
