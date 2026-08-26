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

  @pages [
    "/",
    "/docs",
    "/campaigns",
    "/campaigns/hello-world-climb",
    "/proofs",
    "/start",
    "/climbs",
    "/climbs/hello-world-climb",
    "/proofs/local",
    "/protocol"
  ]
  @pages_without_catalog [
    "/",
    "/docs",
    "/campaigns",
    "/proofs",
    "/start",
    "/climbs",
    "/proofs/local",
    "/protocol"
  ]

  # Two pages name protocol documents on purpose and say so: the protocol map,
  # and the section of a Climb page headed "The documents behind this page".
  # Everywhere else is written for a reader who has never opened one.
  @pages_in_plain_words ["/", "/docs", "/campaigns", "/campaigns/hello-world-climb", "/proofs"]

  describe "with a release being served" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
      Importer.import!(CatalogFixture.root())
      :ok
    end

    test "the local results page states the caveat outright", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/proofs/local")
      text = visible_text(html)

      assert text =~ "Nobody else watched this run"
      assert text =~ "This site did not witness the trial"
      assert text =~ "not the same as an independent"
      assert text =~ "techtree proof verify path/to/result-bundle"
      assert text =~ "There is nowhere to upload a result on this site"
    end

    test "the protocol page maps the documents and links the ones shipped", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/protocol")

      for document <- [
            "DataPolicy",
            "CampaignSpec",
            "ClimbManifest",
            "TasksetValidationReceipt",
            "EpisodeReceipt",
            "UpliftReport",
            "LocalProofBundle",
            "ExperimentManifest"
          ] do
        assert html =~ document
      end

      assert live |> element(~s|a[href="/api/v1/catalog"]|) |> has_element?()

      assert live
             |> element(~s|a[href="/api/v1/objects/#{CatalogFixture.campaign_digest()}"]|)
             |> has_element?()
    end

    test "no page uses the vocabulary of the machinery", %{conn: conn} do
      for page <- @pages do
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

    test "no page offers a form, an upload, or an account", %{conn: conn} do
      for page <- @pages do
        {:ok, _live, html} = live(conn, page)
        markup = String.downcase(html)

        refute markup =~ "<form"
        refute markup =~ "<input"
        refute markup =~ ~s|type="file"|

        # The one control on this site copies a command that is already on the
        # page. Nothing may submit, and nothing may ask the server for anything.
        for [attributes] <-
              Regex.scan(~r/<button([^>]*)>/, markup, capture: :all_but_first) do
          assert attributes =~ ~s|type="button"|, "#{page} has a button that could submit"
          assert attributes =~ "copycommand", "#{page} has a button that is not the copy control"
          refute attributes =~ "phx-click"
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

    test "long values are marked so that they wrap on a narrow screen", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/climbs/hello-world-climb")

      assert html =~ ~s|class="digest"|
      assert html =~ ~s|class="command__block"|
    end

    test "the page frame declares a phone-friendly viewport", %{conn: conn} do
      html = conn |> get("/") |> html_response(200)

      assert html =~ ~s|name="viewport"|
      assert html =~ ~s|content="width=device-width, initial-scale=1"|
      assert html =~ ~s|name="color-scheme"|
    end

    test "pages are sent with a restrictive content policy and no framing", %{conn: conn} do
      conn = get(conn, "/")

      assert get_resp_header(conn, "content-security-policy") == [
               "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; " <>
                 "font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; " <>
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

    test "the protocol page still explains the documents", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/protocol")

      assert html =~ "CampaignSpec"
      assert html =~ "DataPolicy"
      refute html =~ "In this release:"
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
      "verifiers",
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
