defmodule Techtree.WalletBench.Attempt.Changes.AttachCredentials do
  @moduledoc """
  Sends the model key to the machine on standard input (never in a command's
  arguments, which travel in the request's address) and starts the translator
  with it and the attempt's model budget (`credentials.sh attach`), then queues
  the first test, T1a, in the same transaction as the attempt's move to
  `testing`. When the attempt's batch names a Skill, its SKILL.md goes on the
  machine first (`skill.sh`), where the agent's adapter copies it into the
  agent's own skills folder before each turn; the event records its sha256 as
  the machine read it back. Attaching again only replaces the key and the Skill
  and restarts the translator.
  """

  use Ash.Resource.Change

  import Techtree.WalletBench.Attempt.Changes.RecordEvent, only: [put_detail: 2]

  alias Techtree.WalletBench.{Batch, Catalog, Machine, Remote}

  @impl true
  def change(changeset, _opts, _context) do
    changeset
    |> Ash.Changeset.before_transaction(fn changeset ->
      spec = changeset.data.run_spec
      Batch.require_current!(spec)
      budget = budget(spec)

      with {:ok, machine} <- Ash.get(Machine, changeset.data.machine_id),
           {:ok, skill} <- install_skill(machine.name, spec),
           {:ok, "attached\n"} <-
             Remote.run(
               machine.name,
               ["bash", "/work/bin/machine/credentials.sh", "attach", to_string(budget)],
               stdin: model_key(),
               receive_timeout: 240_000
             ) do
        put_detail(
          changeset,
          Map.merge(%{credentials: "attached", model_budget_usd: budget}, skill)
        )
      else
        {:ok, _other} ->
          Ash.Changeset.add_error(
            changeset,
            "credentials.sh attach printed an answer it does not give"
          )

        {:error, error} ->
          Ash.Changeset.add_error(changeset, error)
      end
    end)
    |> Ash.Changeset.after_action(fn _changeset, attempt ->
      Techtree.WalletBench.Turn
      |> Ash.Changeset.for_create(:queue, %{
        attempt_id: attempt.id,
        test: :T1a,
        prompt: Catalog.attempt_prompt(attempt, :T1a)
      })
      # Turns have no public writer; the attempt's own step queues the first.
      |> Ash.create(authorize?: false)
      |> case do
        {:ok, _turn} -> {:ok, attempt}
        {:error, error} -> {:error, error}
      end
    end)
  end

  @doc "The Claude key an attempt's harness calls the model with."
  @spec model_key() :: String.t()
  def model_key, do: Application.fetch_env!(:techtree, Techtree.WalletBench)[:model_key]

  # An attempt outside a batch has the bench's own budget.
  defp budget(nil), do: Catalog.model_budget_usd()
  defp budget(%{"model_budget_usd" => budget}), do: budget

  defp install_skill(_name, nil), do: {:ok, %{}}
  defp install_skill(_name, %{"skill" => nil}), do: {:ok, %{}}

  defp install_skill(name, %{"skill" => %{"name" => skill, "sha256" => sha256}}) do
    case Remote.run(name, ["bash", "/work/bin/machine/skill.sh", skill],
           stdin: Catalog.skill!(skill).body
         ) do
      {:ok, read_back} when read_back == sha256 <> "\n" ->
        {:ok, %{skill: %{name: skill, sha256: sha256}}}

      {:ok, _other} ->
        {:error, "The Skill on the machine is not the one the batch names."}

      {:error, error} ->
        {:error, error}
    end
  end
end
