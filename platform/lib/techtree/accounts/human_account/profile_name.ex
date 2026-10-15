defmodule Techtree.Accounts.HumanAccount.ProfileName do
  @moduledoc """
  The name a person set in their shared Regent profile (edited through
  `/profile`, read through `Techtree.Accounts.SharedProfile`), the same on
  every Regent site signing in with this Privy app; nil until they set one.
  """

  use Ash.Resource.Calculation

  require Ash.Query

  @impl true
  def load(_query, _opts, _context), do: [:privy_user_id]

  @impl true
  def calculate(accounts, _opts, _context) do
    app_id = :techtree |> Application.fetch_env!(:privy) |> Keyword.fetch!(:app_id)
    people = Enum.map(accounts, & &1.privy_user_id)

    # Names are public, so they are read whoever asks; only the name leaves.
    Techtree.Accounts.SharedProfile
    |> Ash.Query.filter(app_id == ^app_id and privy_user_id in ^people)
    |> Ash.Query.select([:privy_user_id, :display_name])
    |> Ash.read(authorize?: false)
    |> case do
      {:ok, profiles} ->
        names = Map.new(profiles, &{&1.privy_user_id, &1.display_name})
        {:ok, Enum.map(accounts, &names[&1.privy_user_id])}

      {:error, error} ->
        {:error, error}
    end
  end
end
