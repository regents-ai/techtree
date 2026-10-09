defmodule Techtree.Accounts do
  @moduledoc "Canonical read-only lookup from a verified shared pairing, never submitted ownership."
  use Ash.Domain
  @behaviour RegentPoints.Accounts
  resources do
    resource Techtree.Accounts.HumanAccount do
      define :by_owner, action: :by_owner, args: [:owner], not_found_error?: false
      define :by_id, action: :by_id, args: [:id]
    end
  end

  @impl true
  def human(id), do: by_id!(id, actor: %{role: :system})
  @impl true
  def agent_names(_id, []), do: {:ok, %{}}

  def agent_names(id, ids) do
    with {:ok, account} <- by_id(id, actor: %{role: :system}),
         {:ok, %{rows: rows}} <-
           Ecto.Adapters.SQL.query(
             Techtree.Repo,
             "SELECT id::text, name FROM regent_agents.pairing_history WHERE privy_user_id = $1 AND id::text = ANY($2::text[])",
             [account.privy_user_id, ids]
           ) do
      {:ok, Map.new(rows, fn [id, name] -> {id, name} end)}
    end
  end
end
