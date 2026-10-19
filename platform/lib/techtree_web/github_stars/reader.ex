defmodule TechtreeWeb.GithubStars.Reader do
  @moduledoc """
  The one process that reads the star count from GitHub, so however many pages
  ask at once, GitHub sees one read. Asks that arrive while a read runs wait
  their turn and find the count fresh.

  A count read is kept for an hour. A failed read leaves the last count in
  place and is tried again after ten minutes.
  """
  use GenServer

  alias TechtreeWeb.GithubStars

  @kept :timer.hours(1)
  @failure_kept :timer.minutes(10)

  def start_link(_options), do: GenServer.start_link(__MODULE__, nil, name: __MODULE__)

  @doc "Asks for a read unless the kept count is fresh. Never waits."
  @spec read() :: :ok
  def read, do: GenServer.cast(__MODULE__, :read)

  @impl GenServer
  def init(nil), do: {:ok, nil}

  @impl GenServer
  def handle_cast(:read, state) do
    unless GithubStars.get!(:fresh) do
      case fetch() do
        {:ok, count} ->
          GithubStars.put!(:count, count)
          GithubStars.put!(:fresh, true, ttl: @kept)

        :none ->
          GithubStars.put!(:fresh, true, ttl: @failure_kept)
      end
    end

    {:noreply, state}
  end

  defp fetch do
    config = Application.fetch_env!(:techtree, :github_stars)

    request = [
      url: "#{config[:api_url]}/repos/#{config[:repository]}",
      headers: [accept: "application/vnd.github+json"],
      receive_timeout: 1_500,
      connect_options: [timeout: 1_500],
      retry: false
    ]

    case Req.get(Keyword.merge(request, Keyword.get(config, :req_options, []))) do
      {:ok, %{status: 200, body: %{"stargazers_count" => count}}}
      when is_integer(count) and count >= 0 ->
        {:ok, count}

      _no_count ->
        :none
    end
  end
end
