defmodule TechtreeWeb.HomeLiveTest do
  @moduledoc """
  The home page: the promise with Book Call, the four services with their
  price levels, the case study from the published Skill comparison, the
  process, the makers whose projects we build on, a last Book Call, and every
  moving picture over a still. Its header, sheet and footer are every page's.
  """

  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture
  alias Techtree.Train.Comparisons
  alias TechtreeWeb.Services
  alias TechtreeWeb.TrainCopy

  @booking "https://calendar.example/techtree"

  setup do
    Application.put_env(:techtree, :book_call, @booking)
    on_exit(fn -> Application.put_env(:techtree, :book_call, nil) end)
  end

  test "the opening has the one page heading, Book Call first and the services next",
       %{conn: conn} do
    {:ok, live, html} = live(conn, ~p"/")
    document = LazyHTML.from_document(html)

    assert [_one] = Enum.to_list(LazyHTML.query(document, "h1"))
    assert has_element?(live, ~s|#hero-title[phx-update="ignore"]|)

    assert hrefs(document, "#hero .rg-button") == [@booking, "#services"]
    assert hrefs(document, "#hero .rg-button--primary[target=_blank]") == [@booking]
    assert hrefs(document, "#begin .rg-button") == [@booking, "mailto:build@regents.sh"]
  end

  test "each service card leads to its page and carries its price level", %{conn: conn} do
    {:ok, live, html} = live(conn, ~p"/")
    document = LazyHTML.from_document(html)

    cards =
      for card <- LazyHTML.query(document, "#services-list > li.mk-service") do
        {attribute(card, "id"), hrefs(card, "a")}
      end

    assert cards ==
             for(
               service <- Services.all(),
               do: {"service-#{service.id}", [Services.path(service.id)]}
             )

    for service <- Services.all() do
      card = "#service-#{service.id}"

      assert has_element?(
               live,
               ~s|#{card} [role="img"][aria-label="Price level #{service.price} of 4"]|
             )

      assert has_element?(live, ~s|#{card} .mk-price__marks[aria-hidden="true"]|)

      marks = Enum.to_list(LazyHTML.query(document, "#{card} .mk-price__mark"))
      filled = Enum.to_list(LazyHTML.query(document, "#{card} .mk-price__mark--on"))
      assert {length(marks), length(filled)} == {4, service.price}
    end

    assert Enum.map(Services.all(), & &1.price) == [1, 2, 3, 4]
    refute has_element?(live, "#service-security")
  end

  test "the case study shows the published Skill comparison's own figures, its page and how to check it",
       %{conn: conn} do
    comparison = Enum.find(Comparisons.list(), &(&1.change == :skill))
    [without, with] = comparison.arms
    tasks = comparison.environment.task_count

    {:ok, _live, html} = live(conn, ~p"/")
    document = LazyHTML.from_document(html)

    figures = for dd <- LazyHTML.query(document, "#case-study-figures dd"), do: trim(dd)

    assert figures == [
             TrainCopy.percent(without.mean_reward),
             TrainCopy.percent(with.mean_reward),
             "#{comparison.paired.wins} of #{tasks}",
             "#{with.solved} of #{tasks}"
           ]

    assert hrefs(document, "#case-study a") == [
             "/train/#{comparison.slug}",
             "/docs/verify#blog-section-skill-comparisons"
           ]
  end

  test "the credits show each maker's logo or name over its projects, every tool among them, and no logo elsewhere",
       %{conn: conn} do
    {:ok, _live, html} = live(conn, ~p"/")
    document = LazyHTML.from_document(html)

    makers =
      for maker <- LazyHTML.query(document, "#stack-list > li.mk-maker") do
        logo = LazyHTML.query(maker, "h3 > img")
        name = LazyHTML.query(maker, "h3.mk-maker__plate--name")

        {attribute(logo, "alt") || trim(name), attribute(logo, "src"),
         hrefs(maker, ".mk-maker__projects a")}
      end

    assert Enum.map(makers, &elem(&1, 0)) ==
             ["Prime Intellect", "NVIDIA", "Nous Research", "Microsoft", "Hugging Face"]

    assert Enum.map(makers, &((elem(&1, 1) || "") =~ ~r|\A/images/built-on/|)) ==
             [true, true, true, false, false]

    assert Enum.all?(makers, fn {_name, _src, links} ->
             links != [] and Enum.all?(links, &String.starts_with?(&1, "https://"))
           end)

    # Every tool from a credited maker sits under that maker.
    credited = Map.new(makers, fn {name, _src, links} -> {name, links} end)

    for tool <- Services.tools(), links = credited[tool.maker] do
      assert tool.href in links, "#{tool.name} is missing from #{tool.maker}'s credits"
    end

    assert Enum.count(LazyHTML.query(document, "img[src*='/images/built-on/']")) == 3

    for path <- [~p"/services/skills", ~p"/results", ~p"/docs", ~p"/about"] do
      refute conn |> get(path) |> html_response(200) =~ "/images/built-on/",
             "#{path} shows a maker's logo"
    end
  end

  test "every moving picture is hidden from screen readers and drawn over a still", %{
    conn: conn
  } do
    {:ok, _live, html} = live(conn, ~p"/")
    document = LazyHTML.from_document(html)
    fields = Enum.to_list(LazyHTML.query(document, ".mk-field"))

    assert length(fields) == 6

    for field <- fields do
      id = attribute(field, "id")
      assert attribute(field, "aria-hidden") == "true", "#{id} is read aloud"
      assert [_still] = Enum.to_list(LazyHTML.query(field, ".mk-field__still"))
      assert [_canvas] = Enum.to_list(LazyHTML.query(field, "canvas##{id}-canvas"))
    end
  end

  test "the page invents no activity, no checking and no relationship", %{conn: conn} do
    {:ok, _live, html} = live(conn, ~p"/")
    text = String.downcase(html)

    for fabrication <- [
          "participants so far",
          "leaderboard",
          "trending",
          "join thousands",
          "independently verified",
          "verified by techtree",
          "partner",
          "official",
          "endorsed",
          "certified",
          "in collaboration with",
          "perfected",
          "affordable"
        ] do
      refute text =~ fabrication
    end

    refute html =~ ~r/\d+\s+(participants|teams|runs|submissions)\b/i
    refute html =~ ~r/\+\d+(\.\d+)?%/
    # A price level, never a figure.
    refute html =~ ~r/\$\s*\d/
  end

  test "its Markdown has the same services, each with its page and price level", %{conn: conn} do
    markdown =
      conn
      |> put_req_header("accept", "text/markdown")
      |> get(~p"/")
      |> response(200)

    for service <- Services.all() do
      assert markdown =~
               "[#{service.name}](#{Services.path(service.id)}): #{service.promise} " <>
                 "Price level: #{service.price} of 4."
    end

    assert markdown =~ "[Security](/services/security)"
    assert markdown =~ "[Book a call](#{@booking})"
    refute markdown =~ ~r/\$\s*\d/
  end

  test "the landing page needs no catalog to render", %{conn: conn} do
    {:ok, live, _html} = live(conn, ~p"/")

    assert has_element?(live, "#services-list")
    assert has_element?(live, "#case-study")
  end

  test "the project source link does not depend on a published release", %{conn: conn} do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())

    {:ok, _live, html} = live(conn, ~p"/")

    assert html =~
             ~s|class="masthead__github" href="https://github.com/regents-ai/techtree" target="_blank"|

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

  test "every page carries the same Services menu, links, Menu sheet and footer",
       %{conn: conn} do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())

    services =
      for service <- Services.all() ++ [Services.security()], do: Services.path(service.id)

    for path <- [
          ~p"/",
          ~p"/docs",
          ~p"/docs/run-locally",
          ~p"/results",
          ~p"/services/evals",
          ~p"/services/security",
          ~p"/climbs/hello-world-climb"
        ] do
      # Read as rendered: the service pages read the sign-in from the socket's
      # connect info, which the LiveView test harness does not carry.
      html = conn |> get(path) |> html_response(200)
      document = LazyHTML.from_document(html)

      # The one menu's button opens its own panel: the four services, then Security.
      assert for(
               trigger <- LazyHTML.query(document, ".masthead__trigger"),
               do: {trim(trigger), attribute(trigger, "popovertarget")}
             ) == [{"Services", "menu-services"}]

      assert [_one] = Enum.to_list(LazyHTML.query(document, "#menu-services[popover]"))
      assert hrefs(document, "#menu-services a") == services

      assert hrefs(document, "#menu-services .menu-columns__column--also a") == [
               "/services/security"
             ]

      assert hrefs(document, ".masthead__link") == ["/results", "/docs"]

      # Below a wide screen, Menu opens the same pages in one sheet; the footer lists them too.
      assert hrefs(document, "#site-menu .menu-columns a") == services
      assert hrefs(document, "#site-menu .sheet__link") == ["/results", "/docs"]

      assert attribute(
               Enum.at(LazyHTML.query(document, ".masthead__menu-button"), 0),
               "popovertarget"
             ) == "site-menu"

      footer = hrefs(document, ".regent-footer__columns a")

      assert Enum.all?(
               services ++ ["/results", "/docs", "/docs/run-locally", "/about"],
               &(&1 in footer)
             )

      assert hrefs(document, ".regent-footer__legal a") == ["/privacy", "/terms"]

      current = hrefs(document, ".masthead__nav a[aria-current=page]")

      case path do
        "/" -> assert current == []
        "/climbs/hello-world-climb" -> assert current == []
        "/docs/run-locally" -> assert current == ["/docs"]
        _page -> assert current == [path]
      end

      # Signed out, the header carries the one theme switch, a real switch.
      assert [_one] = Regex.scan(~r/<button[^>]*role="switch"[^>]*aria-label="Light theme"/, html)
      assert html =~ ~r|<div id="site-theme-switch"[^>]*phx-hook="ThemeSwitch"|

      assert html =~
               ~r|<a class="skip-link" href="#main-content">\s*Skip to main content\s*</a>|

      assert [_one] = Enum.to_list(LazyHTML.query(document, "main#main-content"))
      assert [_one] = Enum.to_list(LazyHTML.query(document, "footer.regent-footer"))
      refute html =~ ~s|>Sign in<|
    end
  end

  test "Book Call shows in the header and its Menu only when a booking page is set", %{conn: conn} do
    docs = fn -> conn |> get(~p"/docs") |> html_response(200) end

    document = LazyHTML.from_document(docs.())
    assert hrefs(document, ".masthead__book[target=_blank]") == [@booking]
    assert hrefs(document, "#site-menu .sheet__end a.rg-button") == [@booking]

    Application.put_env(:techtree, :book_call, nil)
    refute docs.() =~ "Book Call"
  end

  defp hrefs(document, selector) do
    for link <- LazyHTML.query(document, selector), do: attribute(link, "href")
  end

  defp attribute(node, name), do: node |> LazyHTML.attribute(name) |> List.first()
  defp trim(node), do: node |> LazyHTML.text() |> String.trim()
end
