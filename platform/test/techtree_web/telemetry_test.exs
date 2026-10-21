defmodule TechtreeWeb.TelemetryTest do
  use ExUnit.Case, async: false

  import Plug.Test, only: [conn: 2]

  alias Ecto.Adapters.SQL.Sandbox
  alias Techtree.Repo

  # Every site's dashboard reads request and query time by these names, so a
  # request and a query must each land in the scrape.
  test "a request is timed by its route pattern and a query by its whole time" do
    :ok = Sandbox.checkout(Repo)

    :get |> conn("/sitemap.xml") |> TechtreeWeb.Endpoint.call(TechtreeWeb.Endpoint.init([]))
    Repo.query!("SELECT 1")

    scrape = TechtreeWeb.Telemetry.scrape()

    assert scrape =~
             ~r/^techtree_request_duration_microseconds_count\{route="\/sitemap.xml"\} [1-9]/m

    assert scrape =~ ~r/^techtree_repo_query_microseconds_count [1-9]/m
  end
end
