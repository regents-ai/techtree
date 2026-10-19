defmodule TechtreeWeb.GithubStars do
  @moduledoc """
  The repository's GitHub star count for the header, read by the server and drawn
  with the page, so a visitor's browser never calls GitHub (which allows each
  address 60 unsigned reads an hour). A count is kept on this machine for an
  hour; a failed read is kept for ten minutes, during which the header shows no
  count. A page never waits on GitHub: when nothing is kept, it is drawn without
  a count and one read starts beside it, so the pages after it show the count.
  """
  use Nebulex.Cache, otp_app: :techtree, adapter: Nebulex.Adapters.Local

  @kept :timer.hours(1)
  @failure_kept :timer.minutes(10)

  @doc "The kept count, or `:none` while there is none to show."
  @spec count() :: {:ok, non_neg_integer()} | :none
  def count do
    case get!(:count) do
      nil ->
        read_beside()
        :none

      count ->
        count
    end
  end

  @doc "Reads the count from GitHub now and keeps it."
  @spec refresh() :: {:ok, non_neg_integer()} | :none
  def refresh do
    count = read()
    put!(:count, count, ttl: if(count == :none, do: @failure_kept, else: @kept))
    count
  end

  # One read at a time: the first page to find nothing kept starts it.
  defp read_beside do
    if put_new!(:reading, true, ttl: :timer.seconds(5)),
      do: Task.Supervisor.start_child(TechtreeWeb.GithubStars.Reads, &refresh/0)
  end

  defp read do
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

  @doc "A count as the header shows it: `5`, `1.2k`, `3m`."
  @spec compact(non_neg_integer()) :: String.t()
  def compact(count) when count < 1_000, do: Integer.to_string(count)
  def compact(count) when count < 1_000_000, do: tenths(count / 1_000) <> "k"
  def compact(count), do: tenths(count / 1_000_000) <> "m"

  defp tenths(value) do
    rounded = Float.round(value, 1)

    if rounded == trunc(rounded),
      do: Integer.to_string(trunc(rounded)),
      else: Float.to_string(rounded)
  end
end
