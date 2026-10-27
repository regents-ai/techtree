defmodule Techtree.SharedChanges do
  @moduledoc """
  Changes made on any Regent site reach this site's open pages: a Credits balance
  (`RegentCredits.Listener`) and a pairing made or ended (`RegentAgents.Listener`)
  arrive as database notices. Both listen on one connection of the site's own,
  `Techtree.Notifications`, opened with the repository's settings outside its pool.
  The connection starts first, so a new connection brings new listeners.
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
      RegentCredits.Listener,
      RegentAgents.Listener
    ]

    Supervisor.init(children, strategy: :rest_for_one)
  end
end
