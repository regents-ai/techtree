defmodule TechtreeWeb.HealthController do
  @moduledoc """
  Whether this application is serving a catalog, and which one.

  Healthy means there is an active, completed release: the process being up is
  not the same as the site having something true to publish, and a checker that
  cannot tell those apart is worth nothing. Without one, the answer is `503`.

  The answer names the release channel, the import status, the catalog digest,
  and the revision the catalog was generated from. It names no database, no
  host, no path, and no environment variable.

  When the database stops answering, the answer says so (`database_unreachable`)
  rather than that no release is active. For 45 seconds after the last healthy
  answer it still answers healthy, with `database: "unreachable"`, so a brief
  blip doesn't fail the check (`TechtreeWeb.HealthMemory`); after that it is 503.
  """

  use TechtreeWeb, :controller

  alias Techtree.BuildInfo
  alias Techtree.Catalog
  alias Techtree.Catalog.Query
  alias TechtreeWeb.{HealthMemory, Outage}

  @doc """
  Report whether a catalog release is being served.
  """
  def show(conn, _params) do
    summary = Map.put(summary(), :deployed_source_revision, BuildInfo.source_revision())

    conn
    |> put_resp_header("cache-control", "no-store")
    |> put_status(status(summary))
    |> json(summary)
  end

  defp summary do
    case Outage.read(&Query.health_summary/0) do
      {:ok, %{status: :ok} = summary} -> HealthMemory.remember(summary)
      {:ok, summary} -> summary
      :database_down -> HealthMemory.last_healthy() |> unreachable()
    end
  end

  defp unreachable(nil),
    do: %{
      status: :unavailable,
      channel: Catalog.channel(),
      catalog_import_status: :unknown,
      reason: :database_unreachable
    }

  defp unreachable(last_healthy), do: Map.put(last_healthy, :database, "unreachable")

  defp status(%{status: :ok}), do: 200
  defp status(_summary), do: 503
end
