defmodule Techtree.Agents.ActivityReading do
  @moduledoc """
  Each paired agent's reading from the sign-in service (`RegentAgents.Activity`):
  where it has been active across the Regent sites and its registry listing.
  A reading is kept on this machine for five minutes and shared by every page
  that shows the agent, the side panel's list and the Account page's view alike,
  so the service is read at most once per agent in that time. The service answers
  up to 600 reads a minute from a site machine. A read that fails is not kept,
  and the next page to ask reads again.

  A reading is kept under the agent's wallet and pairing time, so an agent paired
  again starts a fresh one.
  """
  use Nebulex.Cache, otp_app: :techtree, adapter: Nebulex.Adapters.Local

  alias RegentAgents.{Activity, PairedAgent}

  @kept :timer.minutes(5)

  @spec read(PairedAgent.t()) :: {:ok, Activity.reading()} | {:error, term()}
  def read(%PairedAgent{} = agent),
    do:
      fetch_or_store({agent.wallet, agent.paired_at}, fn -> Activity.recent(agent) end,
        ttl: @kept
      )
end
