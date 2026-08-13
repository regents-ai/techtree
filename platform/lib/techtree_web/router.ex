defmodule TechtreeWeb.Router do
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
  end

  # The public read-only surface — pages under `:browser`, the exact-byte
  # catalog API under `:api` — is added by the work packages that own it. There
  # are no mutation routes, and an unknown route is a 404 rather than a
  # placeholder.
end
