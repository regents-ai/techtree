defmodule TechtreeWeb.TrainController do
  @moduledoc """
  The comparisons for agents and other sites: `/train.json`, every
  comparison, newest first, each with the addresses of its page and its
  report and its figures; and one comparison's report, as the exact committed
  bytes.

  All of it is public. The comparisons change only with a release, so a caller
  may keep any of it for five minutes and revalidate with its entity tag.
  """

  use TechtreeWeb, :controller

  alias Techtree.Train.Comparisons
  alias TechtreeWeb.ExactResponse

  def index(conn, _params) do
    conn
    |> put_resp_header("cache-control", "public, max-age=300")
    |> json(%{"comparisons" => Enum.map(Comparisons.list(), &entry/1)})
  end

  def report(conn, %{"slug" => slug}) do
    case Comparisons.download(slug) do
      {:ok, bytes, digest} ->
        conn
        |> ExactResponse.put_api_headers()
        |> ExactResponse.send_exact(bytes, "application/json", digest, :revalidated)

      :error ->
        conn
        |> ExactResponse.put_api_headers()
        |> ExactResponse.send_error(
          404,
          :comparison_not_found,
          "no Train comparison has that name",
          "List the comparisons at /train.json."
        )
    end
  end

  # The comparison without its case list, which the report holds.
  defp entry(comparison) do
    comparison
    |> Map.drop([:cases])
    |> Map.merge(%{
      url: url(~p"/train/#{comparison.slug}"),
      report_url: url(~p"/train/#{comparison.slug}/report.json")
    })
  end
end
