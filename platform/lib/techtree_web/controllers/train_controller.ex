defmodule TechtreeWeb.TrainController do
  @moduledoc """
  The comparisons for agents and other sites: `/train.json`, every
  comparison, newest first, each with the addresses of
  its page, its report and its traces; and the two downloads of one
  comparison, its report and its traces, as the exact committed bytes.

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

  def report(conn, %{"slug" => slug}), do: download(conn, slug, :report, "application/json")

  def traces(conn, %{"slug" => slug}),
    do: download(conn, slug, :traces, "application/x-ndjson")

  defp download(conn, slug, file, media_type) do
    case Comparisons.download(slug, file) do
      {:ok, bytes, digest} ->
        conn
        |> ExactResponse.put_api_headers()
        |> ExactResponse.send_exact(bytes, media_type, digest, :revalidated)

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

  defp entry(comparison) do
    %{
      "slug" => comparison.slug,
      "title" => comparison.title,
      "url" => url(~p"/train/#{comparison.slug}"),
      "report_url" => url(~p"/train/#{comparison.slug}/report.json"),
      "traces_url" => url(~p"/train/#{comparison.slug}/traces.jsonl"),
      "digest" => comparison.digest,
      "traces_digest" => comparison.traces_digest,
      "change" => Atom.to_string(comparison.change),
      "outcome" => Atom.to_string(comparison.outcome),
      "environment" => comparison.environment,
      "model" => comparison.model,
      "sampling" => comparison.sampling,
      "software" => comparison.software,
      "arms" => Enum.map(comparison.arms, &arm/1),
      "paired" => paired(comparison.paired),
      "started_at" => DateTime.to_iso8601(comparison.operational.started_at),
      "finished_at" => DateTime.to_iso8601(comparison.operational.finished_at)
    }
  end

  defp arm(arm) do
    %{
      "name" => arm.name,
      "change" => Atom.to_string(arm.change),
      "skill_digest" => arm.skill_digest,
      "adapter" => arm.adapter,
      "mean_reward" => arm.mean_reward,
      "solved" => arm.solved,
      "completion_tokens" => arm.completion_tokens
    }
  end

  defp paired(%{ci95: {low, high}} = paired),
    do:
      paired
      |> Map.put(:ci95, [low, high])
      |> Map.new(fn {key, value} -> {Atom.to_string(key), value} end)
end
