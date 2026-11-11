defmodule TechtreeWeb.AgentAccountController do
  @moduledoc "The current paired agent's read of its person's Points."
  use TechtreeWeb, :controller

  alias RegentPoints.Rules
  alias Techtree.Points.Board
  alias Techtree.SharedReading
  alias TechtreeWeb.{PointsEntries, UnexpectedFailure}

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
