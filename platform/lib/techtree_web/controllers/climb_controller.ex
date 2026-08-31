defmodule TechtreeWeb.ClimbController do
  @moduledoc """
  A convenience view of one public Climb, for choosing between Climbs.

  This is a projection and says so: it carries no protocol schema version, it is
  addressed by slug rather than by digest, and it is assembled from what the
  import already resolved. The scientific objects are linked, not restated — a
  reader who needs the Climb or the Campaign follows `objects` and receives the
  exact bytes with their digest.

  The slug is never used to build a path. It is matched against the references
  the active release imported, so a slug that names nothing is simply a `404`.
  """

  use TechtreeWeb, :controller

  alias Techtree.Catalog.Bundle
  alias Techtree.Catalog.Query
  alias TechtreeWeb.ExactResponse

  @linked_objects [
    {"climb", "climb_digest"},
    {"campaign", "campaign_spec_digest"},
    {"data_policy", "data_policy_digest"},
    {"taskset_validation", "validation_receipt_digest"}
  ]

  @doc """
  Return the public summary of one Climb, and where its objects live.
  """
  def show(conn, %{"slug" => slug}) do
    case Query.get_climb_by_slug(slug) do
      {:ok, entry} ->
        conn
        |> put_resp_header("cache-control", "public, max-age=300")
        |> json(projection(entry))

      {:error, error} ->
        ExactResponse.send_error(conn, error)
    end
  end

  defp projection(entry) do
    entry.projection
    |> Map.put("kind", "climb_summary_projection")
    |> Map.put("objects", linked_objects(entry.projection))
  end

  defp linked_objects(projection) do
    Map.new(@linked_objects, fn {name, key} ->
      digest = Map.fetch!(projection, key)

      {name,
       %{
         "digest" => digest,
         "media_type" => Bundle.json_media_type(),
         "url" => object_url(digest)
       }}
    end)
  end

  # Links are relative, and spell the digest the way the catalog spells it: a
  # reader comparing a link against a digest should not have to decode it first.
  # Every digest here came from the imported index, which is checked digest by
  # digest before an import is allowed, and the controller test follows each of
  # these links through the router to the bytes it promises.
  defp object_url(digest), do: "/api/v1/objects/" <> digest
end
