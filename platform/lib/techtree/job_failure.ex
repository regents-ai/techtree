defmodule Techtree.JobFailure do
  @moduledoc """
  Logs one line for a background job that has run out of attempts, from Oban's
  own event: worker, job id, attempt, error class and up to four causes, never
  the error text. A job's earlier attempts log nothing, so a job that recovers
  on a retry leaves no error line (ash-template f57185c).
  """

  require Logger

  @doc "Logs each job that gives up; called once at start."
  def attach,
    do:
      :telemetry.attach(
        "techtree-job-gave-up",
        [:oban, :job, :exception],
        &__MODULE__.failed/4,
        nil
      )

  @doc false
  def failed(_event, _measurements, %{state: :discard, job: job, reason: error}, _config) do
    Logger.error(
      "Job gave up: worker=#{job.worker} id=#{job.id} attempt=#{job.attempt} class=#{class(error)} causes=#{causes(error)}"
    )
  end

  def failed(_event, _measurements, _metadata, _config), do: :ok

  defp class(%{__struct__: module}) when is_atom(module),
    do: module |> Atom.to_string() |> String.slice(0, 128)

  defp class(_error), do: "unclassified"

  # Only immediate classes, with no recursive inspection of wrapped errors.
  defp causes(%{errors: errors}) when is_list(errors),
    do: errors |> Enum.take(4) |> Enum.map_join(",", &class/1)

  defp causes(_error), do: "none"
end
