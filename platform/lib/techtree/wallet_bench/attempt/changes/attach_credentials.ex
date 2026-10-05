defmodule Techtree.WalletBench.Attempt.Changes.AttachCredentials do
  @moduledoc """
  Sends the model key to the machine on standard input (never in a command's
  arguments, which travel in the request's address) and starts the translator
  with it (`credentials.sh attach`), then queues the first test, T1a, in the
  same transaction as the attempt's move to `testing`. Attaching again only
  replaces the key and restarts the translator.
  """

  use Ash.Resource.Change

  import Techtree.WalletBench.Attempt.Changes.RecordEvent, only: [put_detail: 2]

  alias Techtree.WalletBench.{Catalog, Machine, Remote}

  @impl true
  def change(changeset, _opts, _context) do
    changeset
    |> Ash.Changeset.before_transaction(fn changeset ->
      with {:ok, machine} <- Ash.get(Machine, changeset.data.machine_id),
           {:ok, "attached\n"} <-
             Remote.run(machine.name, ["bash", "/work/bin/machine/credentials.sh", "attach"],
               stdin: model_key(),
               receive_timeout: 240_000
             ) do
        put_detail(changeset, %{credentials: "attached"})
      else
        {:ok, other} ->
          Ash.Changeset.add_error(changeset, "credentials.sh attach printed #{inspect(other)}")

        {:error, error} ->
          Ash.Changeset.add_error(changeset, error)
      end
    end)
    |> Ash.Changeset.after_action(fn _changeset, attempt ->
      Techtree.WalletBench.Turn
      |> Ash.Changeset.for_create(:queue, %{
        attempt_id: attempt.id,
        test: :T1a,
        prompt: Catalog.prompt(:T1a, attempt.harness_id, attempt.wallet_id, nil)
      })
      # Turns have no public writer; the attempt's own step queues the first.
      |> Ash.create(authorize?: false)
      |> case do
        {:ok, _turn} -> {:ok, attempt}
        {:error, error} -> {:error, error}
      end
    end)
  end

  @doc "The OpenAI key an attempt's harness calls the model with."
  @spec model_key() :: String.t()
  def model_key, do: Application.fetch_env!(:techtree, Techtree.WalletBench)[:model_key]
end
