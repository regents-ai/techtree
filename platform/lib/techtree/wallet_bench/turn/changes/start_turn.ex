defmodule Techtree.WalletBench.Turn.Changes.StartTurn do
  @moduledoc """
  Puts the prompt in the turn's folder on the machine and starts `turn.sh` as a
  background job. A turn whose job already exists was started by an earlier
  run of this step and is left alone; the prompt is never rewritten under a
  running turn.
  """

  use Ash.Resource.Change

  alias Techtree.WalletBench.{Attempt, Catalog, Remote}

  @impl true
  def change(changeset, _opts, _context) do
    Ash.Changeset.before_transaction(changeset, fn changeset ->
      turn = changeset.data

      with {:ok, attempt} <-
             Ash.get(Attempt, turn.attempt_id, load: [:machine]),
           :ok <- start(attempt, turn) do
        changeset
      else
        {:error, error} -> Ash.Changeset.add_error(changeset, error)
      end
    end)
  end

  defp start(attempt, turn) do
    name = attempt.machine.name
    folder = Catalog.turn_name(turn.test)
    job = Catalog.turn_job(turn.test)

    case Remote.job_status(name, job) do
      {:ok, :missing} ->
        wallet = Catalog.wallet!(attempt.wallet_id)

        script =
          ["bash", "/work/bin/machine/turn.sh", attempt.harness_id, folder] ++
            [Integer.to_string(Catalog.wall_cap(turn.test)), turn.resume_session_id || "-"] ++
            [wallet.executable | wallet.help]

        with :ok <- bankr_access(attempt, turn),
             {:ok, _stdout} <- put_prompt(name, folder, turn.prompt) do
          Remote.start_job(name, job, script)
        end

      {:ok, _started} ->
        :ok

      {:error, error} ->
        {:error, error}
    end
  end

  # Installation is still unassisted. Only the wallet turn receives the
  # optional benchmark account; the key travels on stdin, never in argv.
  defp bankr_access(%{wallet_id: "W01", machine: machine}, %{test: :T2}) do
    case Application.get_env(:techtree, :wallet_bench_bankr_api_key) do
      key when is_binary(key) and key != "" ->
        case Remote.run(
               machine.name,
               [
                 "sudo",
                 "/.sprite/bin/python3",
                 "/work/bin/machine/bankr_credentials.py",
                 "attach"
               ],
               stdin: key
             ) do
          {:ok, "attached\n"} -> :ok
          {:ok, _other} -> {:error, "Bankr credential attachment did not confirm success."}
          {:error, error} -> {:error, error}
        end

      _not_supplied ->
        :ok
    end
  end

  defp bankr_access(_attempt, _turn), do: :ok

  defp put_prompt(name, folder, prompt) do
    path = "/work/turns/" <> folder

    Remote.run(
      name,
      ["bash", "-c", ~s(install -d -m 700 "$1" && cat > "$1/prompt.txt"), "bash", path],
      stdin: prompt
    )
  end
end
