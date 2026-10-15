defmodule TechtreeWeb.AgentAccountController do
  @moduledoc "Read-only shared account data for the current paired agent; no grant management."
  use TechtreeWeb, :controller

  alias RegentPoints.{Amount, Rules}

  @points_off "Earning Points is off on this site."
  @spending_off "Approving agent spending is off on this site."

  def balances(conn, _params) do
    actor = credit_actor(conn)

    case RegentCredits.agent_budget(actor: actor) do
      {:ok, budget} ->
        answer = %{
          account_id: conn.assigns.publication_actor.human_account_id,
          pairing_id: actor.pairing_id,
          credits: RegentCredits.balance(actor.privy_user_id),
          spending_grant: budget
        }

        conn
        |> put_resp_header("cache-control", "no-store")
        |> json(with_note(answer, not RegentCredits.agent_grants_enabled?(), @spending_off))

      {:error, _error} ->
        unavailable(conn)
    end
  end

  def history(conn, _params) do
    case conn.body_params do
      params when is_map(params) and map_size(params) == 0 ->
        read_history(conn, %{})

      %{"after" => cursor} = params when map_size(params) == 1 and is_binary(cursor) ->
        read_history(conn, %{after: cursor})

      _other ->
        TechtreeWeb.ExactResponse.send_error(
          conn,
          400,
          :invalid_input,
          "Send an empty JSON object or only the after cursor.",
          "Use the cursor from the preceding history page."
        )
    end
  end

  defp read_history(conn, args) do
    case RegentCredits.history(args, actor: credit_actor(conn)) do
      {:ok, history} ->
        answer =
          Map.put(history, :pagination, %{has_more: history.more?, next_cursor: history.next})

        conn |> put_resp_header("cache-control", "no-store") |> json(answer)

      {:error, error} ->
        if cursor_error?(error) do
          TechtreeWeb.ExactResponse.send_error(
            conn,
            422,
            :invalid_cursor,
            "That history cursor is invalid.",
            "Read the first page without after, then use the next_cursor it returns."
          )
        else
          unavailable(conn)
        end
    end
  end

  defp cursor_error?(%Ash.Error.Action.InvalidArgument{field: :after}), do: true
  defp cursor_error?(%Ash.Error.Page.InvalidKeyset{}), do: true

  defp cursor_error?(%Ash.Error.Invalid{errors: [_ | _] = errors}),
    do: Enum.all?(errors, &cursor_error?/1)

  defp cursor_error?(_error), do: false

  def points(conn, _params) do
    paired = conn.assigns.publication_actor

    actor = %{
      role: :agent,
      human_account_id: paired.human_account_id,
      privy_user_id: paired.privy_user_id,
      wallet_address: paired.wallet,
      pairing_id: paired.id
    }

    case RegentPoints.summary(actor: actor) do
      {:ok, summary} ->
        entries =
          Enum.map(
            summary.entries,
            &point_entry/1
          )

        result =
          Map.take(summary, [:balance_micro, :earned_today_micro, :pending, :allowances, :more?])
          |> Map.merge(%{
            points: Amount.format(summary.balance_micro),
            earned_today: Amount.format(summary.earned_today_micro),
            daily_allowances:
              Enum.map(
                summary.allowances,
                &%{scope: &1.scope, remaining: Amount.format(&1.remaining)}
              ),
            entries: entries,
            more: summary.more?
          })

        conn
        |> put_resp_header("cache-control", "no-store")
        |> json(with_note(result, Rules.active() == [], @points_off))

      {:error, _error} ->
        unavailable(conn)
    end
  end

  # Keep the published raw fields while adding the template's readable fields.
  defp point_entry(entry) do
    entry
    |> Map.take([
      :id,
      :rule_id,
      :rule_version,
      :source_app,
      :actor_kind,
      :actor_id,
      :points_micro_delta,
      :earned_at,
      :reason_code
    ])
    |> Map.merge(%{
      points: Amount.format(entry.points_micro_delta),
      source: entry.source_app,
      by: entry.actor_kind
    })
  end

  defp with_note(answer, true, note), do: Map.put(answer, :note, note)
  defp with_note(answer, false, _note), do: answer

  defp credit_actor(conn) do
    actor = conn.assigns.publication_actor
    RegentCredits.Actor.agent(actor.privy_user_id, actor.wallet, "techtree", actor.id)
  end

  defp unavailable(conn),
    do:
      TechtreeWeb.ExactResponse.send_error(
        conn,
        503,
        :account_unavailable,
        "The shared account data could not be read.",
        "Try again with a fresh signed request."
      )
end
