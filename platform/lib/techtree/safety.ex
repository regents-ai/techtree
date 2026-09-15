defmodule Techtree.Safety do
  @moduledoc """
  Choose a test. Compare two monitors. See what they missed.

  A comparison runs two monitor presets over every case of one fixed test
  pack and records each monitor's verdict beside the pack's own label for
  that case. The site funds the model calls, so a day has a cap on how many
  comparisons may start, and the page that starts one says so before the
  button is pressed.
  """

  use Ash.Domain, otp_app: :techtree

  require Ash.Query

  alias Techtree.Safety.Model
  alias Techtree.Safety.Monitor
  alias Techtree.Safety.Run
  alias Techtree.Safety.Runner
  alias Techtree.Safety.TestPack

  @internal [authorize?: false]
  @day_in_seconds 24 * 60 * 60
  @cap_lock 7_215_001

  resources do
    resource Run do
      define :get_run, action: :read, get_by: [:id]
      define :latest_complete_run, action: :latest_complete, args: [:test_slug]
      define :runs_started_since, action: :started_since, args: [:since]
      define :start_run, action: :start
      define :record_verdicts, action: :record_verdicts
      define :finish_run, action: :finish
    end
  end

  @doc "Whether comparisons can start on this site: a model is configured and answering."
  @spec enabled?() :: boolean()
  def enabled?, do: Model.configured().available?()

  @doc "How many comparisons a day this site will start, across everybody."
  @spec daily_run_cap() :: pos_integer()
  def daily_run_cap do
    :techtree
    |> Application.fetch_env!(__MODULE__)
    |> Keyword.fetch!(:daily_run_cap)
  end

  @doc "How many comparisons may still start today."
  @spec runs_left_today() :: non_neg_integer()
  def runs_left_today do
    since = DateTime.add(DateTime.utc_now(), -@day_in_seconds, :second)
    started = runs_started_since!(since, @internal) |> length()
    Kernel.max(daily_run_cap() - started, 0)
  end

  @doc """
  Start one comparison and return the run the results page will follow.

  Refused, with a reason a reader can be shown, when comparisons are not
  switched on, the day's cap is spent, the pack or a preset is unknown, or
  the two presets are the same monitor.
  """
  @spec start_comparison(String.t(), String.t(), String.t()) ::
          {:ok, Run.t()} | {:error, String.t()}
  def start_comparison(test_slug, monitor_a, monitor_b) do
    with {:ok, pack} <- pack(test_slug),
         {:ok, a} <- preset(monitor_a),
         {:ok, b} <- preset(monitor_b),
         :ok <- different(a, b),
         :ok <- switched_on(),
         {:ok, run} <- admit(pack, a, b) do
      {:ok, _pid} = Runner.start(run)
      {:ok, run}
    end
  end

  @doc "Stop a running comparison, keeping every verdict recorded so far."
  @spec cancel(Run.t()) :: Run.t()
  def cancel(%Run{} = run), do: Runner.cancel(run)

  @doc "The PubSub topic a run's progress is broadcast on."
  @spec topic(String.t()) :: String.t()
  def topic(run_id), do: "safety:run:" <> run_id

  @doc "Fetch one run by id, without authorization ceremony: runs are public."
  @spec fetch_run(String.t()) :: {:ok, Run.t()} | :error
  def fetch_run(id) do
    case Ecto.UUID.cast(id) do
      {:ok, uuid} ->
        case get_run(uuid, @internal) do
          {:ok, run} -> {:ok, run}
          {:error, _reason} -> :error
        end

      :error ->
        :error
    end
  end

  @doc "The most recent complete run of a pack, if there is one."
  @spec example_run(String.t()) :: Run.t() | nil
  def example_run(test_slug) do
    case latest_complete_run(test_slug, @internal) do
      {:ok, run} -> run
      {:error, _reason} -> nil
    end
  end

  @doc false
  def internal_options, do: @internal

  defp pack(slug) do
    case TestPack.fetch(slug) do
      {:ok, pack} -> {:ok, pack}
      :error -> {:error, "there is no test called #{slug}"}
    end
  end

  defp preset(key) do
    case Monitor.fetch(key) do
      {:ok, preset} -> {:ok, preset}
      :error -> {:error, "there is no monitor called #{key}"}
    end
  end

  defp different(%{key: key}, %{key: key}), do: {:error, "choose two different monitors"}
  defp different(_a, _b), do: :ok

  defp switched_on do
    if enabled?(), do: :ok, else: {:error, "comparisons are not switched on for this site"}
  end

  # The cap is checked and the run recorded under one lock, so two presses at
  # the day's last slot cannot both start.
  defp admit(pack, a, b) do
    # Ash.transaction rolls back on an `{:error, _}` return, so a refusal
    # travels out under its own tag.
    {:ok, outcome} =
      Ash.transaction(Run, fn ->
        Techtree.Repo.query!("SELECT pg_advisory_xact_lock($1)", [@cap_lock])

        case under_cap() do
          :ok -> {:admitted, start_run!(run_attributes(pack, a, b), @internal)}
          {:error, reason} -> {:refused, reason}
        end
      end)

    case outcome do
      {:admitted, run} -> {:ok, run}
      {:refused, reason} -> {:error, reason}
    end
  end

  defp run_attributes(pack, a, b) do
    %{
      test_slug: pack.slug,
      test_version: pack.version,
      monitor_a: a.key,
      monitor_b: b.key,
      model: Techtree.Safety.Model.Anthropic.model(),
      case_count: length(pack.cases)
    }
  end

  defp under_cap do
    if runs_left_today() > 0,
      do: :ok,
      else: {:error, "today's #{daily_run_cap()} free comparisons have all been used"}
  end
end
