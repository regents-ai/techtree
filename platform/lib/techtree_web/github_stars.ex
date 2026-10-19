defmodule TechtreeWeb.GithubStars do
  @moduledoc """
  The repository's GitHub star count for the header, read by the server and drawn
  with the page, so a visitor's browser never calls GitHub (which allows each
  address 60 unsigned reads an hour).

  A page only ever reads the count kept on this machine; it never waits on
  GitHub. When the kept count is more than an hour old, or ten minutes after a
  read that failed, the page asks `TechtreeWeb.GithubStars.Reader` for a new
  read, and the pages after it show the new count. A read that fails keeps the
  last count; the header shows none only until the first read succeeds.
  """
  use Nebulex.Cache, otp_app: :techtree, adapter: Nebulex.Adapters.Local

  alias TechtreeWeb.GithubStars.Reader

  @doc "The kept count, or `:none` before any read has succeeded."
  @spec count() :: {:ok, non_neg_integer()} | :none
  def count do
    unless get!(:fresh), do: Reader.read()

    case get!(:count) do
      nil -> :none
      count -> {:ok, count}
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
