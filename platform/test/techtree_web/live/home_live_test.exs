defmodule TechtreeWeb.HomeLiveTest do
  @moduledoc """
  The home page: one promise and its actions, the projects Techtree is built
  on, Evaluate & Climb at the core, the products in groups, the On-ramp to
  Prime Intellect, and every moving picture over a still.
  """

  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture
  alias Techtree.NetworkFixture
  alias TechtreeWeb.HomeLive
  alias TechtreeWeb.SiteMenu

  describe "with a release published" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
      Importer.import!(CatalogFixture.root())
      :ok
    end

    test "the opening has the one page heading, one Start and the agent's instruction",
         %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/")
      document = LazyHTML.from_document(html)

      assert ["Techtree"] = for(h1 <- LazyHTML.query(document, "h1"), do: trim(h1))
      assert has_element?(live, "#hero h1#hero-title")
      assert has_element?(live, ~s|#hero-display[phx-update="ignore"]|)
      assert hrefs(document, "#hero .rg-button--primary") == ["/start"]
      assert copied_text(html, "copy-home-agent-line") == HomeLive.agent_line()

      # With nothing published there is no Result to turn through.
      refute has_element?(live, "#hero-results")
    end

    test "Evaluate & Climb is the core: its statement, the first Measure item and the first menu entry",
         %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/")
      document = LazyHTML.from_document(html)

      assert has_element?(live, "#evaluate h2#evaluate-title", "Evaluate & Climb")

      assert [first | _rest] = Enum.to_list(LazyHTML.query(document, "#measure details"))
      assert attribute(first, "open") != nil
      assert first |> LazyHTML.query("summary h3") |> trim() == "Evaluate & Climb"
      assert "/start" in hrefs(first, "a")

      [entry | _rest] = Enum.to_list(LazyHTML.query(document, "#menu-products .menu-page"))
      assert attribute(entry, "href") == "/start"
      assert entry |> LazyHTML.query(".menu-page__name") |> trim() == "Evaluate & Climb"
    end

    test "SkillEvaluator is credited with a link, and its checks are marked Soon", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/")
      document = LazyHTML.from_document(html)
      skill_evaluator = "https://github.com/NVIDIA/SkillEvaluator"

      for place <- ["#hero", "#evaluate", "#measure", "#stack"] do
        assert skill_evaluator in hrefs(document, "#{place} a"),
               "#{place} leaves out SkillEvaluator's link"
      end

      soon =
        for card <- LazyHTML.query(document, "#evaluate .mk-card"),
            into: %{},
            do:
              {card |> LazyHTML.query("h4") |> trim(),
               Enum.any?(LazyHTML.query(card, ".mk-soon"))}

      assert %{"Validate" => true, "Deduplicate" => true, "Live run" => false} = soon
      assert has_element?(live, ~s|#stack-list a[href="#{skill_evaluator}"] .mk-soon|)
    end

    test "the Stack shows each maker's logo over that maker's projects, and no logo elsewhere",
         %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/")
      document = LazyHTML.from_document(html)

      makers =
        for maker <- LazyHTML.query(document, "#stack-list > li.mk-maker") do
          logo = LazyHTML.query(maker, "h3 > img")
          tiles = Enum.map(LazyHTML.query(maker, "a.mk-tile"), &stack_tile/1)
          {attribute(logo, "alt"), attribute(logo, "src"), tiles}
        end

      expected =
        for projects <- Enum.chunk_by(SiteMenu.stack().pages, & &1.by) do
          tiles = for page <- projects, do: {page.href, page.by, page.name}
          {String.trim_trailing(hd(projects).by, "’s"), tiles}
        end

      assert for({name, _src, tiles} <- makers, do: {name, tiles}) == expected
      assert Enum.map(makers, &elem(&1, 0)) == ["Prime Intellect", "NVIDIA", "Nous Research"]
      assert Enum.all?(makers, fn {_name, src, _tiles} -> src =~ ~r|\A/images/built-on/| end)
      assert Enum.all?(SiteMenu.stack().pages, &String.starts_with?(&1.href, "https://"))

      assert Enum.count(LazyHTML.query(document, "img[src*='/images/built-on/']")) ==
               length(makers)

      assert hrefs(document, "#stack-list a.mk-tile--path") == ["#onramp"]
    end

    test "the On-ramp runs from your work through Techtree to Prime Intellect", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/")
      document = LazyHTML.from_document(html)

      assert has_element?(live, "#onramp.mk-dark h2#onramp-title")

      assert for(
               stop <- LazyHTML.query(document, "#onramp-path > li"),
               do: stop |> LazyHTML.query("h3") |> trim()
             ) ==
               ["Your work", "Techtree", "Prime Intellect"]

      # A link into each stop after the first, drawn and never read aloud.
      assert [_, _] =
               Enum.to_list(
                 LazyHTML.query(document, ~s|#onramp-path [data-link][aria-hidden="true"]|)
               )

      assert [] =
               Enum.to_list(LazyHTML.query(document, "#onramp-path > li:first-child [data-link]"))

      # Techtree's mark, square by square, in the middle stop.
      for part <- ["data-outline", "data-block"] do
        assert length(
                 Enum.to_list(LazyHTML.query(document, ".mk-path__stop--techtree [#{part}]"))
               ) == 13
      end

      assert "https://www.primeintellect.ai/" in hrefs(document, "#onramp-path a")
      assert "mailto:build@regents.sh" in hrefs(document, "#onramp a")
    end

    test "each product group opens one item at a time and pictures the open one", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/")
      document = LazyHTML.from_document(html)

      for group <- ["measure", "prove", "build"] do
        items = Enum.to_list(LazyHTML.query(document, "##{group} details.mk-item"))
        assert length(items) > 1
        assert Enum.all?(items, &(attribute(&1, "name") == group))
        assert [open] = Enum.filter(items, &attribute(&1, "open"))

        [picture] = Enum.to_list(LazyHTML.query(document, "##{group}-picture"))
        assert attribute(picture, "data-field-shape") == attribute(open, "data-shape")
      end
    end

    test "every moving picture is hidden from screen readers and drawn over a still", %{
      conn: conn
    } do
      {:ok, _live, html} = live(conn, ~p"/")
      document = LazyHTML.from_document(html)
      fields = Enum.to_list(LazyHTML.query(document, ".mk-field"))

      assert length(fields) >= 7

      for field <- fields do
        id = attribute(field, "id")
        assert attribute(field, "aria-hidden") == "true", "#{id} is read aloud"
        assert [_still] = Enum.to_list(LazyHTML.query(field, ".mk-field__still"))
        assert [_canvas] = Enum.to_list(LazyHTML.query(field, "canvas##{id}-canvas"))
      end
    end

    test "the newest news leads to its changelog day or its post", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/")
      cards = html |> LazyHTML.from_document() |> hrefs("#news .mk-news__card")

      assert length(cards) in 1..3

      assert Enum.all?(cards, fn href ->
               String.starts_with?(href, "/changelog#blog-section-website-") or
                 String.starts_with?(href, "/blog/")
             end)
    end

    @tag :tmp_dir
    test "the command line is one copyable release-derived block", %{conn: conn, tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)
      CatalogFixture.rewrite_bootstrap!(bundle, &CatalogFixture.concrete_release/1)
      CatalogFixture.use_bundle(bundle)
      Importer.import!(bundle)

      {:ok, live, html} = live(conn, ~p"/")
      release = TechtreeWeb.ReleaseInfo.current()

      expected =
        Enum.join(release.install_argv, " ") <>
          "\n" <>
          "regents techtree forge inspect-skill path/to/your-skill"

      assert has_element?(live, "#agents-cli #copy-home-cli")
      assert copied_text(html, "copy-home-cli") == expected
    end

    test "the page invents no activity, no checking and no relationship", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/")
      text = String.downcase(html)

      for fabrication <- [
            "participants so far",
            "runs completed",
            "leaderboard",
            "trending",
            "join thousands",
            "independently verified",
            "verified by techtree",
            "partner",
            "official",
            "endorsed",
            "certified",
            "in collaboration with"
          ] do
        refute text =~ fabrication
      end

      refute html =~ ~r/\d+\s+(participants|teams|runs|submissions)\b/i
      refute html =~ ~r/\+\d+(\.\d+)?%/
    end
  end

  describe "with a Result published" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
      Importer.import!(CatalogFixture.root())
      files = NetworkFixture.resign(NetworkFixture.scored(), keys: NetworkFixture.key_pair())
      {:ok, entry, :recorded} = NetworkFixture.publish(NetworkFixture.submission(files))
      {:ok, entry: entry}
    end

    test "the newest Result sits in the middle of the opening, with its figures and how sure it is",
         %{conn: conn, entry: entry} do
      {:ok, live, html} = live(conn, ~p"/")
      card = ~s|#hero-newest-result[data-carousel-card][data-slot="centre"]|
      verdict = entry.assessment |> Techtree.Network.Verdict.of() |> Atom.to_string()

      assert has_element?(
               live,
               ~s|#{card} .mk-result__link[href="/results/#{entry.bundle_digest}"]|,
               "Hello World Skill vs baseline"
             )

      assert has_element?(live, "#{card} .verdict--#{verdict}")
      assert has_element?(live, card, "1 run")

      figures =
        for figure <- LazyHTML.query(LazyHTML.from_document(html), "#{card} [data-figure]"),
            do: trim(figure)

      assert figures == Enum.map([entry.wins, entry.ties, entry.losses], &to_string/1)

      # One Result does not turn: no dots and no Pause.
      refute has_element?(live, "#hero-results button")
      assert has_element?(live, ~s|#figures a[href="/results"] [data-tally]|, "1")
    end
  end

  test "the landing page needs no catalog to render", %{conn: conn} do
    {:ok, live, html} = live(conn, ~p"/")

    assert visible_text(html) =~ HomeLive.agent_line()
    refute html =~ "copy-home-cli"
    refute has_element?(live, "#hero-results")
  end

  test "the project source link does not depend on a published release", %{conn: conn} do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())

    {:ok, _live, html} = live(conn, ~p"/")

    assert html =~
             ~s|class="masthead__github" href="https://github.com/regents-ai/techtree" target="_blank"|

    assert html =~ "Star on GitHub"
    refute html =~ "masthead__github-mark"
  end

  test "the sheet shares canonical type, spacing and control skins" do
    css = File.read!(Path.expand("../../../assets/css/app.css", __DIR__))

    assert css =~ ~s|@import "../vendor/regent_ui/primitives.css"|
    assert css =~ ~s|@import "./techtree_home.css"|
    assert css =~ "font-family: var(--font-family-ui)"
    assert css =~ "font-family: var(--font-family-title)"
    assert css =~ "font-synthesis: none"
    refute css =~ "100vw;"
    refute css =~ "text-overflow: ellipsis"
  end

  test "small-screen controls retain data and intentional table scrolling" do
    css = File.read!(Path.expand("../../../assets/css/app.css", __DIR__))

    assert css =~ "@media (max-width: 24rem)"
    assert css =~ "grid-template-columns: minmax(0, 1fr)"
    assert css =~ ".runs-index__table-frame"
    assert css =~ "overflow-x: auto"
    refute css =~ ~r/\.runs-table__runtime\s*\{[^}]*display: none/s
    assert css =~ ~r/\.command__copy\s*\{[^}]*min-height: 2\.75rem;/s
    assert css =~ ~r/\.tasks__filter\s*\{[^}]*min-height: 2\.75rem;/s
    assert css =~ ~r/\.pagecopy__main\s*\{[^}]*min-height: 2\.75rem;/s
  end

  test "the landing page leaves every primary tab neutral", %{conn: conn} do
    {:ok, _live, html} = live(conn, ~p"/")

    refute html =~ ~s|aria-current="page"|
    assert html =~ ~s|<a class="masthead__name" href="/" aria-label="Techtree home">|
    refute html =~ ~s|<a class="masthead__name" data-phx-link|
  end

  test "every page carries the same three menus, the same Menu sheet and the same footer",
       %{conn: conn} do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())
    stack = for page <- SiteMenu.stack().pages, do: page.href

    for path <- [
          ~p"/",
          ~p"/docs",
          ~p"/results",
          ~p"/verify",
          ~p"/start",
          ~p"/climbs/hello-world-climb"
        ] do
      {:ok, live, html} = live(conn, path)
      document = LazyHTML.from_document(html)

      # Each menu's button opens its own panel.
      assert for(
               trigger <- LazyHTML.query(document, ".masthead__trigger"),
               do: {trim(trigger), attribute(trigger, "popovertarget")}
             ) == [
               {"Products", "menu-products"},
               {"Agents", "menu-agents"},
               {"Resources", "menu-resources"}
             ]

      for panel <- ["menu-products", "menu-agents", "menu-resources"] do
        assert [_one] = Enum.to_list(LazyHTML.query(document, "##{panel}[popover]"))
      end

      menus = hrefs(document, "[data-mega] a")

      for page <- ~w(/start /results /wallet-bench /train /verify /formal /repo2rlenv
                     /services/verify /services/cyber-assist /services/watchdog /agents
                     /agents.md /llms.txt /docs/api /docs /changelog /blog /about) do
        assert page in menus, "#{path}: the menus leave out #{page}"
      end

      # Resources ends with the Stack, each entry naming whose project it is.
      assert hrefs(document, "#menu-resources .menu-columns__column:last-child a") == stack

      assert length(Enum.to_list(LazyHTML.query(document, "#menu-resources .menu-page__by"))) ==
               length(stack)

      # Below a wide screen, Menu opens the same pages in one sheet; the footer lists them too.
      assert hrefs(document, "#site-menu .menu-columns a") == menus

      assert attribute(
               Enum.at(LazyHTML.query(document, ".masthead__menu-button"), 0),
               "popovertarget"
             ) == "site-menu"

      footer = hrefs(document, ".regent-footer__columns a")
      assert Enum.all?(menus, &(&1 in footer))
      assert hrefs(document, ~s|ul[aria-labelledby="footer-stack"] a|) == stack
      assert hrefs(document, ".regent-footer__legal a") == ["/privacy", "/terms"]

      current = hrefs(document, "[data-mega] a[aria-current=page]")
      if path in [~p"/start", ~p"/docs", ~p"/results", ~p"/verify"], do: assert(current == [path])
      if path == ~p"/climbs/hello-world-climb", do: assert(current == [])

      # Signed out, the header carries the one theme switch, a real switch.
      assert [_one] = Regex.scan(~r/<button[^>]*role="switch"[^>]*aria-label="Light theme"/, html)
      assert html =~ ~r|<div id="site-theme-switch"[^>]*phx-hook="ThemeSwitch"|
      assert has_element?(live, "main")

      assert html =~
               ~r|<a class="skip-link" href="#main-content">\s*Skip to main content\s*</a>|

      assert has_element?(live, "main#main-content")
      assert has_element?(live, "footer.regent-footer")
      refute html =~ ~s|>Sign in<|
    end
  end

  test "Book Call shows in the header and its Menu only when a booking page is set", %{conn: conn} do
    address = "https://calendar.example/techtree"
    docs = fn -> conn |> get(~p"/docs") |> html_response(200) end

    refute docs.() =~ "Book Call"

    Application.put_env(:techtree, :book_call, address)
    on_exit(fn -> Application.put_env(:techtree, :book_call, nil) end)

    document = LazyHTML.from_document(docs.())
    assert hrefs(document, ".masthead__book[target=_blank]") == [address]
    assert hrefs(document, "#site-menu .sheet__end a.rg-button") == [address]
  end

  defp hrefs(document, selector) do
    for link <- LazyHTML.query(document, selector), do: attribute(link, "href")
  end

  # A Stack tile as its address, whose project it is and its name, without Soon.
  defp stack_tile(tile) do
    name = tile |> LazyHTML.query(".mk-tile__name") |> trim() |> String.replace(~r/\s*Soon$/, "")
    {attribute(tile, "href"), tile |> LazyHTML.query(".mk-tile__by") |> trim(), name}
  end

  defp attribute(node, name), do: node |> LazyHTML.attribute(name) |> List.first()
  defp trim(node), do: node |> LazyHTML.text() |> String.trim()
end
