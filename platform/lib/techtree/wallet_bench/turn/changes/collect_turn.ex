defmodule Techtree.WalletBench.Turn.Changes.CollectTurn do
  @moduledoc """
  Waits (an Oban snooze) while the turn runs on the machine. Once it has ended,
  brings the turn's whole folder back as one archive, reads the tested
  account's secrets on the machine (`secrets.py`, held in memory only), blanks
  every file (`Techtree.WalletBench.Blank`) and stores each under
  `attempts/<attempt>/<turn>/` in the evidence bucket. The turn records each
  file's sha256 and size, the harness's conversation id, exit code and timing,
  and what the tested model's calls cost.

  A turn whose runner was lost (the machine restarted) or ended badly is
  `failed` at once, with the end of its log. Storing again replaces the same
  keys with the same bytes.
  """

  use Ash.Resource.Change

  import Techtree.WalletBench.Attempt.Changes.RecordEvent, only: [put_detail: 2]

  alias Techtree.WalletBench.{Attempt, Blank, Catalog, Evidence, Remote}
  alias Techtree.WalletBench.Attempt.Changes.AttachCredentials

  @wait_seconds 30

  @impl true
  def change(changeset, _opts, _context) do
    Ash.Changeset.before_transaction(changeset, fn changeset ->
      turn = changeset.data

      with {:ok, attempt} <-
             Ash.get(Attempt, turn.attempt_id, load: [:machine]),
           {:ok, status} <- Remote.job_status(attempt.machine.name, Catalog.turn_job(turn.test)) do
        ended(changeset, status, attempt, turn.test)
      else
        {:error, error} -> Ash.Changeset.add_error(changeset, error)
      end
    end)
  end

  defp ended(changeset, :running, _attempt, _test),
    do:
      Ash.Changeset.add_error(
        changeset,
        AshOban.Errors.SnoozeJob.exception(snooze_for: @wait_seconds)
      )

  defp ended(changeset, {:exit, 0}, attempt, test) do
    case collect(attempt, Catalog.turn_name(test)) do
      {:ok, attributes, detail} ->
        changeset
        |> Ash.Changeset.force_change_attributes(attributes)
        |> put_detail(detail)

      {:error, error} ->
        Ash.Changeset.add_error(changeset, error)
    end
  end

  defp ended(changeset, status, attempt, test) do
    how =
      case status do
        {:exit, code} -> "ended with exit code #{code}"
        :lost -> "stopped without finishing"
        :missing -> "was never started"
      end

    case Remote.job_log_tail(attempt.machine.name, Catalog.turn_job(test)) do
      {:ok, log} ->
        reason = "The turn's runner #{how}."

        changeset
        |> Ash.Changeset.force_change_attributes(%{state: :failed, failure: reason})
        |> put_detail(%{failure: reason, log_tail: log})

      {:error, error} ->
        Ash.Changeset.add_error(changeset, error)
    end
  end

  defp collect(attempt, folder) do
    name = attempt.machine.name
    archive = ~s(tar -C "/work/turns/$1" -czf - . | base64 -w0)

    with {:ok, encoded} <-
           Remote.run(name, ["bash", "-c", archive, "bash", folder], receive_timeout: 180_000),
         {:ok, files} <- unpack(encoded),
         {:ok, %{"files" => secret_files}} <-
           Remote.json(name, ["sudo", "/.sprite/bin/python3", "/work/bin/machine/secrets.py"]) do
      known = [{AttachCredentials.model_key(), "API key"} | Blank.from_files(secret_files)]
      blanked = Map.new(files, fn {file, content} -> {file, Blank.blank(content, known)} end)

      with :ok <- store(attempt, folder, blanked) do
        {:ok, attributes(blanked),
         %{files: map_size(blanked), secret_files: Enum.map(secret_files, & &1["path"])}}
      end
    end
  end

  defp unpack(encoded) do
    with {:ok, archive} <- Base.decode64(encoded),
         {:ok, entries} <- :erl_tar.extract({:binary, archive}, [:compressed, :memory]) do
      {:ok,
       Map.new(entries, fn {name, content} ->
         {name |> to_string() |> Path.basename(), content}
       end)}
    else
      :error -> {:error, "The turn's archive did not decode."}
      {:error, reason} -> {:error, "The turn's archive did not unpack: #{inspect(reason)}"}
    end
  end

  defp store(attempt, folder, blanked) do
    Enum.reduce_while(blanked, :ok, fn {file, content}, :ok ->
      case Evidence.put(Evidence.turn_key(attempt.id, folder, file), content, content_type(file)) do
        :ok -> {:cont, :ok}
        {:error, error} -> {:halt, {:error, error}}
      end
    end)
  end

  defp attributes(files) do
    summary = Jason.decode!(Map.fetch!(files, "turn-summary.json"))

    %{
      session_id: summary["session_id"],
      exit_code: files |> Map.fetch!("exit_code") |> String.trim() |> String.to_integer(),
      started_at: moment(files, "start_utc"),
      ended_at: moment(files, "end_utc"),
      wall_seconds: files |> Map.fetch!("wall_seconds") |> String.trim() |> Decimal.new(),
      model_spend_usd: spend(Map.fetch!(files, "model-calls.jsonl")),
      evidence:
        Map.new(files, fn {file, content} ->
          {file, %{sha256: sha256(content), bytes: byte_size(content)}}
        end)
    }
  end

  defp moment(files, file) do
    {:ok, at, 0} = files |> Map.fetch!(file) |> String.trim() |> DateTime.from_iso8601()
    at
  end

  # What the translator counted for each answered call in the turn.
  defp spend(calls) do
    calls
    |> String.split("\n", trim: true)
    |> Enum.map(&Jason.decode!/1)
    |> Enum.filter(&(&1["event"] == "answered"))
    |> Enum.reduce(Decimal.new(0), &Decimal.add(Decimal.from_float(&1["cost"]), &2))
  end

  defp content_type(file) do
    case Path.extname(file) do
      ".json" -> "application/json"
      ".jsonl" -> "application/x-ndjson; charset=utf-8"
      ".md" -> "text/markdown; charset=utf-8"
      _other -> "text/plain; charset=utf-8"
    end
  end

  defp sha256(content), do: :crypto.hash(:sha256, content) |> Base.encode16(case: :lower)
end
