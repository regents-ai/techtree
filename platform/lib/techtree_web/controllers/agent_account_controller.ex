defmodule TechtreeWeb.AgentAccountController do
  @moduledoc "Read-only shared account data for the current paired agent; no grant management."
  use TechtreeWeb, :controller

  def balances(conn, _params) do
    actor = credit_actor(conn)

    permission =
      RegentCredits.agent_permissions!(actor: actor)
      |> Enum.find(
        &(&1.agent_address == actor.agent_address and &1.pairing_id == actor.pairing_id)
      )

    budget =
      if permission do
        Map.take(permission, [:enabled, :max_per_spend, :daily_limit, :sites])
        |> Map.put(:used_24h, RegentCredits.AgentSpending.spent_today(actor))
      else
        %{enabled: false}
      end

    conn
    |> put_resp_header("cache-control", "no-store")
    |> json(%{
      account_id: conn.assigns.publication_actor.human_account_id,
      pairing_id: actor.pairing_id,
      credits: RegentCredits.balance(actor.privy_user_id),
      spending_grant: budget
    })
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
      {:ok, history} -> conn |> put_resp_header("cache-control", "no-store") |> json(history)
      {:error, _error} -> unavailable(conn)
    end
  end

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
            &Map.take(&1, [
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
          )

        result =
          Map.take(summary, [:balance_micro, :earned_today_micro, :pending, :allowances, :more?])

        conn
        |> put_resp_header("cache-control", "no-store")
        |> json(Map.put(result, :entries, entries))

      {:error, _error} ->
        unavailable(conn)
    end
  end

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
