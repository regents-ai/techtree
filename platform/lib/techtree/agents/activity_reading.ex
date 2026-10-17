defmodule Techtree.Agents.ActivityReading do
  @moduledoc """
  Each paired agent's reading from the sign-in service (`RegentAgents.Activity`):
  where it has been active across the Regent sites and its registry listing.
  A reading is kept on this machine for five minutes and shared by every page
  that shows the agent, the side panel's list and the Account page's view alike,
  so the service is read at most once per agent in that time. The service answers
  up to 600 reads a minute from a site machine. A failed read is kept for one
  minute, so while the service is down each agent is asked again at most once a
  minute, however often the panel opens.

  A reading is kept under the agent's wallet and pairing time, so an agent paired
  again starts a fresh one.

  Each read that gives no reading is counted in `health.agent_activity_unread.total`
  by its reason, such as `bad_day` for a day from the service in a shape it does not
  send.
  """
  use Nebulex.Cache, otp_app: :techtree, adapter: Nebulex.Adapters.Local

  alias RegentAgents.{Activity, PairedAgent}

  @kept :timer.minutes(5)
  @failure_kept :timer.minutes(1)

  @spec read(PairedAgent.t()) :: {:ok, Activity.reading()} | {:error, term()}
  def read(%PairedAgent{} = agent) do
    key = {agent.wallet, agent.paired_at}

    case get!(key) do
      nil -> read_and_keep(key, agent)
      reading -> reading
    end
  end

  defp read_and_keep(key, agent) do
    reading = Activity.recent(agent)
    put!(key, reading, ttl: kept(reading))
    measure(reading)
    reading
  end

  defp kept({:ok, _reading}), do: @kept
  defp kept({:error, _reason}), do: @failure_kept

  defp measure({:ok, _reading}), do: :ok

  defp measure({:error, reason}),
    do:
      :telemetry.execute([:techtree, :agents, :activity_unread], %{count: 1}, %{
        reason: reason(reason)
      })

  defp reason(reason)
       when reason in [:bad_day, :bad_days, :registration_unreadable, :not_configured],
       do: reason

  defp reason({:unexpected_status, _status}), do: :unexpected_status
  defp reason(_unanswered), do: :unanswered
end
