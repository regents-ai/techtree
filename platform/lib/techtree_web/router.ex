defmodule TechtreeWeb.Router do
  @moduledoc """
  Every route this application answers.

  All but one of them are `GET`. The exception is `POST /api/v1/publications`,
  where a participant publishes a finished run and, later, withdraws one they
  published. Two documents, one address: each declares what it is in a member
  its own signature covers, so which one arrived is read off the document rather
  than off the URL, and this site keeps the single write address decision 0038
  allows it. What is done with either is in `Techtree.Network.Ingest`, which
  checks every property of a bundle before a row exists and checks a withdrawal
  against the key the entry already carries before an event is appended. There
  is no route that uploads a file, authenticates anybody, or ranks anything, and
  no route takes a path parameter other than a digest, a key fingerprint, or a
  slug the catalog can resolve. A request for anything else is a `404`, never a
  placeholder that appears to have worked.

  A run is addressed by its bundle digest, at `/runs/<digest>` and at
  `/api/v1/publications/<digest>`. That address is derivable from the proof
  itself, two people publishing the same bundle land on the same page, and
  nothing in it reads as a rank — a row identifier would exist only inside our
  own database, and a log sequence in a URL would look like a position.

  `GET /api/v1/publication-keys/:key_id` is the counterpart of that one write:
  the public half of the key this site signs publication receipts with,
  at the fingerprint of that key, so a receipt can be checked by anybody
  holding one and the address can be derived from the receipt rather than
  looked up.

  The endpoint also declares the live-page transport the public pages use.
  Nothing reachable through it can write: every catalog and network resource
  forbids create, update, and destroy through any interface, and the importer
  and the ingest are the two callers that bypass that, deliberately and each in
  one place.
  """

  use TechtreeWeb, :router

  @content_security_policy "default-src 'none'; script-src 'self'; style-src 'self'; " <>
                             "img-src 'self' data:; font-src 'self'; connect-src 'self'; " <>
                             "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"

  pipeline :browser do
    plug :accepts, ["html"]
    plug :fetch_session
    plug :fetch_live_flash
    plug :put_root_layout, html: {TechtreeWeb.Layouts, :root}
    plug :protect_from_forgery

    plug :put_secure_browser_headers, %{
      "content-security-policy" => @content_security_policy,
      "referrer-policy" => "no-referrer"
    }
  end

  pipeline :api do
    plug :accepts, ["json"]
    plug :put_public_api_headers
  end

  # The one pipeline in front of the one address that accepts a body.
  pipeline :publishing do
    plug :accepts, ["json"]
    plug :put_public_api_headers
    plug TechtreeWeb.PublicationRate
  end

  scope "/", TechtreeWeb do
    pipe_through :browser

    live "/", HomeLive
    live "/docs", DocsLive
    live "/campaigns", CampaignsLive.Index
    live "/campaigns/:slug", CampaignsLive.Show
    live "/proofs", ProofsLive
    live "/proofs/local", LocalProofLive
    live "/runs", RunsLive.Index
    live "/runs/:bundle_digest", RunsLive.Show
    get "/skill.md", SkillController, :show

    # The addresses release documents already point at, unchanged.
    live "/start", StartLive
    live "/climbs", ClimbsLive.Index
    live "/climbs/:slug", ClimbsLive.Show
    live "/protocol", ProtocolLive
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
    get "/publications", PublicationController, :index
    get "/publications/:bundle_digest", PublicationController, :show
    get "/publication-keys/:key_id", PublicationKeyController, :show
  end

  # The one address that accepts anything, on its own so that what stands in
  # front of it is visible here rather than buried in a pipeline everything
  # shares.
  scope "/api/v1", TechtreeWeb do
    pipe_through :publishing

    post "/publications", PublicationController, :create
  end

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
