defmodule Techtree.Accounts.HumanAccount.AnnounceRegistration do
  @moduledoc """
  Emits `:account_registered` when the sign-in inserted the account. A sign-in
  to an account that already exists skips the upsert, and Ash marks the account
  it returns with `upsert_skipped`.
  """

  use Ash.Resource.Change

  alias Techtree.Accounts.Signals

  @impl true
  def change(changeset, _opts, _context) do
    Ash.Changeset.after_action(changeset, fn
      _changeset, %{__metadata__: %{upsert_skipped: true}} = account ->
        {:ok, account}

      changeset, account ->
        with :ok <-
               Ash.Signals.emit(changeset, Signals, :account_registered, %{account_id: account.id}),
             do: {:ok, account}
    end)
  end
end
