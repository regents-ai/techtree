defmodule Techtree.Jobs.Watch do
  @moduledoc """
  Every five minutes, once `read_payments` is on (the Oban crontab in
  `config/config.exs`), makes sure the staking contract has its reading job
  (`Techtree.Jobs.ReadPayments`): inserting it again finds the one already
  there, and a new one runs at once. `refresh/0` brings that job's next run
  forward when the agent or the team asks to look now.
  """

  use Oban.Worker, queue: :jobs_chain, max_attempts: 1

  alias Techtree.Jobs.{Payment, ReadPayments}

  # Two early reads are at least this far apart, so many presses cost one read.
  @gap_seconds 10

  @impl Oban.Worker
  def perform(%Oban.Job{}) do
    Oban.insert!(job())
    :ok
  end

  @doc """
  Brings the reading job's next run forward to ten seconds from now when it is
  due later; one due sooner keeps its time, so presses that keep coming never
  put the read off. Nothing is read while `read_payments` is off.
  """
  @spec refresh() :: :ok
  def refresh do
    if Payment.config()[:read_payments] do
      soon = DateTime.add(DateTime.utc_now(), @gap_seconds)
      job() |> Oban.insert!() |> bring_forward(soon)
    end

    :ok
  end

  defp bring_forward(%Oban.Job{state: state, scheduled_at: at} = job, soon)
       when state in ["scheduled", "retryable"] do
    if DateTime.after?(at, soon), do: {:ok, _job} = Oban.update_job(job, %{scheduled_at: soon})
  end

  defp bring_forward(%Oban.Job{}, _soon), do: :ok

  defp job do
    settings = Payment.config()
    ReadPayments.new(%{chain_id: settings[:chain_id], contract: settings[:staking]})
  end
end
