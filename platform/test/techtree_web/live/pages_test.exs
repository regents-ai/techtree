defmodule TechtreeWeb.PagesTest do
  @moduledoc """
  What every page owes a reader, whatever else is on it: honest wording about
  what this site did and did not witness, no implementation vocabulary, and
  markup that survives a phone.
  """

  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture
  alias Techtree.NetworkFixture

  @pages [
    "/",
    "/docs",
    "/research",
    "/proofs",
    "/start",
    "/climbs/hello-world-climb",
    "/results",
    "/results/" <> Techtree.NetworkFixture.bundle_digest()
  ]
  @pages_without_catalog [
    "/",
    "/docs",
    "/research",
    "/proofs",
    "/start",
    "/results"
  ]

  # Every human-facing page is written for a reader who has never opened a
  # protocol document.
  @pages_in_plain_words [
    "/",
    "/proofs",
    "/start",
    "/climbs/hello-world-climb",
    "/results",
    "/results/" <> Techtree.NetworkFixture.bundle_digest()
  ]

  # Research carries the long-form method and roadmap. It may use
  # the technical terms and bare library name that the shorter product pages
  # deliberately avoid.
  @product_pages List.delete(@pages, "/research")

  describe "with a release being served" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
      Importer.import!(CatalogFixture.root())
      {:ok, _entry, :recorded} = NetworkFixture.publish()
      :ok
    end

    test "initial HTML identifies its deployed source and omits disconnect copy", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/results")

      assert html =~ ~s|<meta name="techtree-revision" content="development"/>|
      refute visible_text(html) =~ "The connection to the site dropped"
      refute html =~ "The connection to the site dropped"
    end

    test "every page mounts the theme-aware vGPU background with a solid fallback", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/results")

      assert html =~
               ~s|id="site-background" class="site-background" data-optics-kind="background" data-optics-source="/assets/js/background_island.js"|

      assert html =~
               ~s|id="site-background-canvas" class="site-background__canvas" data-optics-canvas|

      assert html =~ ~s|data-background-theme="orange"|
      assert html =~ ~s|data-background-preset="10"|
    end

    test "no page uses the vocabulary of the machinery", %{conn: conn} do
      for page <- @product_pages do
        {:ok, _live, html} = live(conn, page)
        body = html |> visible_text() |> String.downcase()

        for word <- forbidden_words() do
          refute body =~ word, "#{page} says #{inspect(word)}"
        end
      end
    end

    test "no page names the machinery where a reader is being spoken to", %{conn: conn} do
      for page <- @pages_in_plain_words do
        {:ok, _live, html} = live(conn, page)
        body = html |> visible_text() |> String.downcase()

        for word <- protocol_words() do
          refute body =~ word, "#{page} says #{inspect(word)} to a reader"
        end
      end
    end

    test "Verifiers is only ever named in a sanctioned form", %{conn: conn} do
      # Founder rulings 2026-08-26: the site credits Prime Intellect's
      # Verifiers by name; the founder-worded lede may call the environment
      # kind a "verifiers environment"; and the hover card may define the
      # word ("verifiers is a library by Prime Intellect..."). A hover term
      # sits directly against its own card, so a bare occurrence is also fine
      # when the definition follows it immediately. Anything else is refused.
      for page <- @product_pages do
        {:ok, _live, html} = live(conn, page)
        body = html |> visible_text() |> String.downcase()
        parts = String.split(body, "verifiers", trim: false)
        last = length(parts) - 2

        base =
          for index <- 0..max(last, 0)//1, into: %{} do
            before = Enum.at(parts, index, "")
            after_ = parts |> Enum.at(index + 1, "") |> String.trim_leading()

            {index,
             String.ends_with?(before, ["prime intellect's ", "prime intellect’s "]) or
               String.starts_with?(after_, [
                 "environment",
                 "is a library by prime intellect"
               ])}
          end

        bare =
          for index <- 0..max(last, 0)//1,
              last >= 0,
              not Map.get(base, index, true),
              not (String.trim(Enum.at(parts, index + 1, "x")) == "" and
                     Map.get(base, index + 1, false)),
              do: index

        assert bare == [],
               "#{page} says 'verifiers' outside the sanctioned forms"
      end
    end

    test "no page offers a form, an upload, or an account", %{conn: conn} do
      for page <- @pages do
        {:ok, _live, html} = live(conn, page)
        markup = String.downcase(html)

        refute markup =~ "<form"
        refute markup =~ "<input"
        refute markup =~ ~s|type="file"|

        # Most controls are local-only. The proof detail's task filters ask the
        # LiveView to show a subset of evidence but submit no data.
        for [attributes] <-
              Regex.scan(~r/<button([^>]*)>/, markup, capture: :all_but_first) do
          assert attributes =~ ~s|type="button"|, "#{page} has a button that could submit"

          assert attributes =~ "copycommand" or attributes =~ "data-theme-toggle" or
                   attributes =~ ~s|phx-click="filter_tasks"|,
                 "#{page} has a button that is not a local-only control"

          if attributes =~ "phx-click" do
            assert attributes =~ ~s|phx-click="filter_tasks"|
          end
        end

        # Nothing on the page invites a reader to identify themselves.
        links = Regex.scan(~r/<a [^>]*>(.*?)<\/a>/s, markup, capture: :all_but_first)

        for [label] <- links do
          refute label =~ "sign in"
          refute label =~ "log in"
          refute label =~ "sign up"
          refute label =~ "register"
          refute label =~ "upload"
        end
      end
    end

    test "nothing on a page can force a phone to scroll sideways", %{conn: conn} do
      for page <- @pages do
        {:ok, _live, html} = live(conn, page)

        # No fixed pixel widths, and no table: the long values on these pages are
        # fingerprints and commands, which wrap or scroll inside their own box.
        refute html =~ ~r/style="[^"]*width:\s*\d{3,}px/
        refute html =~ ~r/<table/
        refute html =~ ~r/white-space:\s*nowrap/
      end
    end

    test "the page frame declares a phone-friendly viewport", %{conn: conn} do
      html = conn |> get("/") |> html_response(200)

      assert html =~ ~s|name="viewport"|
      assert html =~ ~s|content="width=device-width, initial-scale=1"|
      assert html =~ ~s|name="color-scheme"|
    end

    test "a saved color theme is applied by the first server render", %{conn: conn} do
      html =
        conn
        |> put_req_cookie("techtree_theme", "orange")
        |> get("/")
        |> html_response(200)

      assert html =~ ~s|<html lang="en" data-theme="orange">|
    end

    test "orange is the default regardless of system preference", %{conn: conn} do
      html = conn |> get("/") |> html_response(200)

      assert html =~ ~s|<html lang="en" data-theme="orange">|
      assert html =~ ~s|<meta name="color-scheme" content="light">|
    end

    test "a saved titanium choice overrides the orange default", %{conn: conn} do
      html =
        conn
        |> put_req_cookie("techtree_theme", "titanium")
        |> get("/")
        |> html_response(200)

      assert html =~ ~s|<html lang="en" data-theme="titanium">|
      assert html =~ ~s|<meta name="color-scheme" content="dark">|
    end

    test "pages are sent with a restrictive content policy and no framing", %{conn: conn} do
      conn = get(conn, "/")

      assert get_resp_header(conn, "content-security-policy") == [
               "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; " <>
                 "font-src 'self'; connect-src 'self' https://api.github.com; base-uri 'none'; " <>
                 "form-action 'none'; " <>
                 "frame-ancestors 'none'"
             ]

      assert get_resp_header(conn, "x-content-type-options") == ["nosniff"]
      assert get_resp_header(conn, "referrer-policy") == ["no-referrer"]
    end
  end

  describe "with nothing imported" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
    end

    test "every page that does not name a Climb still renders", %{conn: conn} do
      for page <- @pages_without_catalog do
        assert {:ok, _live, html} = live(conn, page)
        assert html =~ "A Regents Labs project"
      end
    end

    test "a Climb page is not found rather than empty", %{conn: conn} do
      assert_error_sent 404, fn -> live(conn, ~p"/climbs/hello-world-climb") end
    end
  end

  # The names of protocol documents and of the machinery that produces them.
  # Each is the right word in a specification and the wrong word on a page
  # somebody is reading to decide whether to install something.
  defp protocol_words do
    [
      "campaignspec",
      "climbmanifest",
      "datapolicy",
      "tasksetvalidationreceipt",
      "episodereceipt",
      "upliftreport",
      "localproofbundle",
      "experimentmanifest",
      "schema",
      "enum",
      "manifest",
      "projection"
    ]
  end

  defp forbidden_words do
    [
      "liveview",
      "backward compat",
      "fallback",
      "hard cutover",
      "server-rendered",
      "api wiring",
      "digest mismatch",
      "deserialize",
      "serialize",
      "changeset",
      "postgres",
      "database",
      "json payload",
      "http 4",
      "http 5"
    ]
  end
end
