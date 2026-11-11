defmodule Techtree.Watchdog.EnforceCap do
  @moduledoc """
  Holds a person to a fixed number of Watchdog rows of one kind, so one account
  cannot fill the table. The create takes a per-account advisory lock inside its
  own transaction, counts the account's existing rows of that resource, and adds
  an error when the count has reached the cap. The lock is held until the
  transaction ends, so two creates for the same account cannot both pass the
  count and both insert.

  Pattern adapted from ash-template's capped list
  (`AshTemplate.Notes.Decision.UnderDailyBudget`); the lock is taken in the
  create's own `before_action` so the count is read under it.

  Options:

    * `:resource` — the Ash resource whose rows are counted.
    * `:limit` — the key in `config :techtree, Techtree.Watchdog` holding the cap.
    * `:message` — the error shown when the cap is reached.
  """

  use Ash.Resource.Change

  require Ash.Query

  alias Techtree.Watchdog.Limits

  @impl true
  def change(changeset, opts, context) do
    resource = Keyword.fetch!(opts, :resource)
    limit = Limits.fetch!(Keyword.fetch!(opts, :limit))
    message = Keyword.fetch!(opts, :message)

    Ash.Changeset.before_action(changeset, fn changeset ->
      account_id = Ash.Changeset.get_attribute(changeset, :human_account_id)
      :ok = lock(resource, account_id)

      # The cap counts the account's own rows, already scoped to this account's
      # id; only the number is used, never the rows, so the per-row read policy
      # is not applied here (the same reasoning as ash-template's capped list).
      count =
        resource
        |> Ash.Query.filter(human_account_id == ^account_id)
        |> Ash.count!(authorize?: false, tenant: context.tenant)

      if count < limit,
        do: changeset,
        else: Ash.Changeset.add_error(changeset, field: :base, message: message)
    end)
  end

  defp lock(resource, account_id) do
    key = :erlang.phash2({resource, account_id})
    Techtree.Repo.query!("SELECT pg_advisory_xact_lock($1)", [key])
    :ok
  end
end
