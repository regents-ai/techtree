defmodule TechtreeWeb.Router do
  @moduledoc """
  Every route this application answers.

  All of them are `GET`. There is no route that creates, accepts, uploads,
  authenticates, or ranks anything, and there is no route that takes a path
  parameter other than a digest or a slug the catalog can resolve. A request for
  anything else is a `404`, never a placeholder that appears to have worked.

  The endpoint also declares the live-page transport the public pages will use.
  Nothing reachable through it can write either: every catalog resource forbids
  create, update, and destroy through any interface, and the importer is the one
  caller that bypasses that, deliberately and in one place.
  """

  use TechtreeWeb, :router

  pipeline :browser do
    plug :accepts, ["html"]
    plug :fetch_session
    plug :fetch_live_flash
    plug :put_root_layout, html: {TechtreeWeb.Layouts, :root}
    plug :protect_from_forgery
    plug :put_secure_browser_headers
  end

  pipeline :api do
    plug :accepts, ["json"]
    plug :put_public_api_headers
  end

  scope "/", TechtreeWeb do
    pipe_through :api

    get "/healthz", HealthController, :show
  end

  scope "/api/v1", TechtreeWeb do
    pipe_through :api

    get "/bootstrap", BootstrapController, :show
    get "/catalog", CatalogController, :index
    get "/climbs/:slug", ClimbController, :show
    get "/objects/:digest", ObjectController, :show
  end

  # The public pages are added by the work package that owns them; they will use
  # the `:browser` pipeline above.

  # An API response is data, never a document: nothing in it may be sniffed into
  # a content type it did not declare, loaded as a page resource, framed, or
  # allowed to leak a referrer.
  defp put_public_api_headers(conn, _opts) do
    conn
    |> put_resp_header("x-content-type-options", "nosniff")
    |> put_resp_header("content-security-policy", "default-src 'none'; frame-ancestors 'none'")
    |> put_resp_header("x-frame-options", "DENY")
    |> put_resp_header("referrer-policy", "no-referrer")
  end
end
