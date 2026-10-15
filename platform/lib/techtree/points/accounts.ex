defmodule Techtree.Points.Accounts do
  @moduledoc "Verified account lookups supplied to the shared Points package."
  @behaviour RegentPoints.Accounts

  alias Techtree.Accounts
  alias Techtree.Actors.System

  @impl true
  def human(id), do: Accounts.points_account!(id, actor: %System{})

  @impl true
  def agent_names(_id, []), do: {:ok, %{}}

  def agent_names(id, ids) do
    # The canonical account supplies the owner; historical episodes retain names.
    with {:ok, account} <- Accounts.points_account(id, actor: %System{}),
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
