defmodule Techtree.Projects.Project.TeamMember do
  @moduledoc """
  Records the admin who delivered or withdrew a project: their account, and
  the name it showed then (`id` and `name` name the two attributes). The admin
  is the actor, never an input.

  It runs once the action's policy has let the admin through, so the actor is
  always one of the site's admins.
  """

  use Ash.Resource.Change

  alias Techtree.Accounts
  alias Techtree.Actors.{Human, System}

  @impl true
  def change(changeset, opts, %{actor: actor}),
    do: Ash.Changeset.before_action(changeset, &record(&1, opts, actor))

  defp record(changeset, opts, %RegentAgents.Person{privy_user_id: id}) do
    case Accounts.get_by_privy_did(id, actor: %System{}) do
      {:ok, %{} = account} ->
        Ash.Changeset.force_change_attributes(changeset, [
          {opts[:id], account.id},
          {opts[:name], Human.for_account(account).name}
        ])

      {:ok, nil} ->
        Ash.Changeset.add_error(changeset, "Your account couldn't be read. Sign in again.")

      {:error, error} ->
        Ash.Changeset.add_error(changeset, error)
    end
  end
end
