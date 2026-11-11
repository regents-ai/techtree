defmodule Techtree.SharedChanges do
  @moduledoc """
  Changes made on any Regent site reach this site's open pages: a pairing made or
  ended (`RegentAgents.Listener`) arrives as a database notice. It listens on a
  connection of the site's own, `Techtree.Notifications`, opened with the
  repository's settings outside its pool. The connection starts first, so a new
  connection brings a new listener.
  """

  use Supervisor

  def start_link(_opts), do: Supervisor.start_link(__MODULE__, nil, name: __MODULE__)

  @impl true
  def init(nil) do
    connection =
      Techtree.Repo.config()
      |> Keyword.drop([:pool, :pool_size, :parameters])
      |> Keyword.merge(auto_reconnect: true, parameters: [application_name: "techtree-listen"])

    children = [
      {Postgrex.Notifications, [name: Techtree.Notifications] ++ connection},
      RegentAgents.Listener
    ]

    Supervisor.init(children, strategy: :rest_for_one)
  end
end
