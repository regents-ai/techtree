defmodule TechtreeWeb.HealthController do
  @moduledoc """
  Whether this machine is serving a catalog: `/healthz` in plain text for the
  host's health check, `ok` or `503 unavailable`.

  Serving means there is an active, completed catalog release: the process being
  up is not the same as the site having something true to publish. Which
  release and which commit are served is read elsewhere: the release at
  `/api/v1/bootstrap`, the commit at `/capabilities.json`.

  For 45 seconds after the last `ok`, a check that meets a database that stops
  answering still answers `ok`, so a brief blip doesn't fail the check
  (`TechtreeWeb.HealthMemory`); after that it is 503.
  """

  use TechtreeWeb, :controller

  alias Techtree.Catalog.Query
  alias TechtreeWeb.{HealthMemory, Outage}

  def show(conn, _params) do
    {status, body} = if serving?(), do: {:ok, "ok"}, else: {:service_unavailable, "unavailable"}

    conn
    |> put_resp_header("cache-control", "no-store")
    |> put_resp_content_type("text/plain")
    |> send_resp(status, body)
  end

  defp serving? do
    case Outage.read(&Query.active_catalog_release/0) do
      {:ok, {:ok, _release}} ->
        HealthMemory.remember()
        true

      {:ok, {:error, _no_release}} ->
        false

      :database_down ->
        HealthMemory.recent?()
    end
  end
end
