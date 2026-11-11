defmodule TechtreeWeb.AgentAccountController do
  @moduledoc "Read-only shared account data for the current paired agent; no grant management."
  use TechtreeWeb, :controller

  alias RegentPoints.Rules
  alias Techtree.Points.Board
  alias Techtree.SharedReading
  alias TechtreeWeb.{PointsEntries, UnexpectedFailure}

  @points_off "Earning Points is off on this site."
  @spending_closed "Agent spending isn't open yet. Your person can do this themselves."
  @spending_ask "Your person can allow you to spend Credits on this site on their Regents account at regents.sh/account."

  # What the agent may spend, and the note, both come from the agent's budget
  # (`RegentCredits.agent_budget/1`): its grant, and whether a grant can be made.
  def balances(conn, _params) do
    actor = credit_actor(conn)

    case RegentCredits.agent_budget(actor: actor) do
      {:ok, budget} ->
        answer = %{credits: RegentCredits.balance(actor.privy_user_id), spending_grant: budget}
        private_json(conn, with_note(answer, spending_note(budget)))

      {:error, error} ->
        conn |> UnexpectedFailure.log(error) |> unavailable()
    end
  end

  defp spending_note(%{site_allowed: true}), do: nil
  defp spending_note(%{grant_approvals_available: false}), do: @spending_closed
  defp spending_note(%{grant_approvals_available: true}), do: @spending_ask

  def credits_history(%{body_params: %{"after" => cursor}} = conn, _params)
      when not is_binary(cursor),
      do: invalid_cursor(conn)

  def credits_history(conn, _params) do
    args =
      case conn.body_params do
        %{"after" => cursor} when is_binary(cursor) -> %{after: cursor}
        _ -> %{}
      end

    case RegentCredits.history(args, actor: credit_actor(conn)) do
      {:ok, history} ->
        private_json(conn, %{
          entries: history.entries,
          pagination: %{has_more: history.more?, next_cursor: history.next}
        })

      {:error, error} ->
        if cursor_error?(error) do
          invalid_cursor(conn)
        else
          conn |> UnexpectedFailure.log(error) |> unavailable()
        end
    end
  end

  defp cursor_error?(%Ash.Error.Action.InvalidArgument{field: :after}), do: true
  defp cursor_error?(%Ash.Error.Page.InvalidKeyset{}), do: true

  defp cursor_error?(%Ash.Error.Invalid{errors: [_ | _] = errors}),
    do: Enum.all?(errors, &cursor_error?/1)

  defp cursor_error?(_error), do: false

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

  defp credit_actor(conn) do
    actor = conn.assigns.actor

    RegentCredits.Actor.agent(
      actor.privy_user_id,
      actor.wallet_address,
      Techtree.site(),
      actor.pairing_id
    )
  end

  defp invalid_cursor(conn),
    do:
      TechtreeWeb.ExactResponse.send_error(
        conn,
        422,
        :invalid_cursor,
        "That cursor is invalid.",
        "Send after as the previous page's pagination.next_cursor, unchanged, or omit it for the newest entries."
      )

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
