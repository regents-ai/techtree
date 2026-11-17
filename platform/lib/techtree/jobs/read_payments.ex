defmodule Techtree.Jobs.ReadPayments do
  @moduledoc """
  Keeps one staking contract's job payments current on one chain: the one
  reading job for that contract, unique while it is incomplete, on whichever
  machine took it. Each run proves the node serves the chain, makes one
  `Techtree.Jobs.Scanner` pass, then waits five minutes and runs again.
  `Techtree.Jobs.Watch.refresh/0` brings the next run forward to ten seconds
  away, never later, and the watch makes sure the job exists.

  The contract's cursor opens at the head on the job's first run, so a deposit
  made before then is never read.

  A node that does not answer is one warning line and a minute's wait, never a
  failure. Any other failed pass is retried a minute later; a job that has
  failed 20 times is given up, and the watch starts a fresh one. A node that
  serves another chain is never read: the job stops, with an error logged.
  """

  use Oban.Worker,
    queue: :jobs_chain,
    max_attempts: 20,
    unique: [keys: [:chain_id, :contract], period: :infinity, states: :incomplete]

  require Logger

  alias Techtree.Jobs.{Scanner, Staking}

  @pass_interval 300
  @retry_after 60

  @impl Oban.Worker
  def perform(%Oban.Job{args: %{"chain_id" => chain_id, "contract" => contract}}) do
    with {:ok, ^chain_id} <- Staking.chain_id(),
         :ok <- Scanner.pass(%{chain_id: chain_id, contract: contract}) do
      {:snooze, @pass_interval}
    else
      {:ok, other_chain} ->
        Logger.error(
          "Job payments on #{contract} are on chain #{chain_id}, but the node serves " <>
            "#{other_chain}; not reading them"
        )

        {:cancel, {:wrong_chain, other_chain}}

      {:error, :unavailable} ->
        Logger.warning(
          "Job payments on #{contract} not read: the node did not answer; reading again in a minute"
        )

        {:snooze, @retry_after}

      {:error, reason} ->
        {:error, reason}
    end
  end

  @impl Oban.Worker
  def backoff(%Oban.Job{}), do: @retry_after
end
