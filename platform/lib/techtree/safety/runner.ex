defmodule Techtree.Safety.Runner do
  @moduledoc """
  The process that evaluates one run: both monitors over every case, verdicts
  recorded as each case finishes, progress broadcast to whoever is watching.

  One task per run, under a supervisor, registered by run id. Cancelling
  closes the run as cancelled with whatever was recorded; every write the
  runner makes applies only while the run is still running, so its next
  write after that is refused and it stops, and the model calls still in
  flight are discarded rather than recorded against a run that is over. A
  crash closes the run as failed the same way. Neither ever writes `complete`.
  """

  require Logger

  alias Techtree.Safety
  alias Techtree.Safety.Model
  alias Techtree.Safety.Monitor
  alias Techtree.Safety.Run
  alias Techtree.Safety.TestPack

  @supervisor Techtree.Safety.Runners
  @registry Techtree.Safety.RunRegistry
  @max_concurrency 4

  @doc "The children the application supervises for runs."
  @spec child_specs() :: [Supervisor.child_spec()]
  def child_specs do
    [
      {Registry, keys: :unique, name: @registry},
      {Task.Supervisor, name: @supervisor}
    ]
  end

  @doc "Start evaluating a run that was just recorded."
  @spec start(Run.t()) :: {:ok, pid()}
  def start(%Run{} = run) do
    Task.Supervisor.start_child(@supervisor, fn -> evaluate(run) end)
  end

  @doc "The process evaluating a run, if it is still going."
  @spec whereis(String.t()) :: pid() | nil
  def whereis(run_id) do
    case Registry.lookup(@registry, run_id) do
      [{pid, _value}] -> pid
      [] -> nil
    end
  end

  @doc "Close a run as cancelled, keeping its verdicts. The runner stops at its next write."
  @spec cancel(Run.t()) :: Run.t()
  def cancel(%Run{} = run) do
    case close(run, :cancelled, nil) do
      {:ok, cancelled} -> cancelled
      :closed -> latest(run)
    end
  end

  defp evaluate(%Run{} = run) do
    {:ok, _owner} = Registry.register(@registry, run.id, nil)
    {:ok, pack} = TestPack.fetch(run.test_slug)
    {:ok, a} = Monitor.fetch(run.monitor_a)
    {:ok, b} = Monitor.fetch(run.monitor_b)
    model = Model.configured()

    try do
      pack.cases
      |> Task.async_stream(
        fn recorded ->
          [
            Monitor.evaluate(a, pack, recorded, :a, model),
            Monitor.evaluate(b, pack, recorded, :b, model)
          ]
        end,
        max_concurrency: @max_concurrency,
        ordered: false,
        timeout: :infinity
      )
      |> Enum.reduce_while(run, fn {:ok, verdicts}, current ->
        case record(current, verdicts) do
          {:ok, recorded} -> {:cont, recorded}
          :closed -> {:halt, :closed}
        end
      end)
      |> case do
        :closed -> :ok
        %Run{} = finished -> close(finished, :complete, nil)
      end
    rescue
      exception ->
        Logger.error("safety run #{run.id} failed: " <> Exception.message(exception))
        close(run, :failed, Exception.message(exception))
    end
  end

  defp record(%Run{} = run, verdicts) do
    run
    |> Safety.record_verdicts(%{verdicts: run.verdicts ++ verdicts}, Safety.internal_options())
    |> written()
  end

  defp close(%Run{} = run, status, failure) do
    run
    |> Safety.finish_run(%{status: status, failure: failure}, Safety.internal_options())
    |> written()
  end

  # A write is refused once the run is closed; that is the runner's signal to stop.
  defp written({:ok, %Run{} = run}) do
    broadcast(run)
    {:ok, run}
  end

  defp written({:error, %Ash.Error.Invalid{errors: errors} = error}) do
    if Enum.any?(errors, &match?(%Ash.Error.Changes.StaleRecord{}, &1)),
      do: :closed,
      else: raise(error)
  end

  defp latest(%Run{} = run) do
    {:ok, latest} = Safety.fetch_run(run.id)
    latest
  end

  defp broadcast(%Run{} = run) do
    Phoenix.PubSub.broadcast(Techtree.PubSub, Safety.topic(run.id), {:safety_run, run})
  end
end
