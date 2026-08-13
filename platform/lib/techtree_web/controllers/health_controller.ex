defmodule TechtreeWeb.HealthController do
  @moduledoc """
  Whether this application is serving a catalog, and which one.

  Healthy means there is an active, completed release: the process being up is
  not the same as the site having something true to publish, and a checker that
  cannot tell those apart is worth nothing. Without one, the answer is `503`.

  The answer names the release channel, the import status, the catalog digest,
  and the revision the catalog was generated from. It names no database, no
  host, no path, and no environment variable.
  """

  use TechtreeWeb, :controller

  alias Techtree.Catalog.Query

  @doc """
  Report whether a catalog release is being served.
  """
  def show(conn, _params) do
    summary = Query.health_summary()

    conn
    |> put_resp_header("cache-control", "no-store")
    |> put_status(status(summary))
    |> json(summary)
  end

  defp status(%{status: :ok}), do: 200
  defp status(_summary), do: 503
end
