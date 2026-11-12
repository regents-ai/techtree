defmodule TechtreeWeb.Layouts do
  @moduledoc """
  The frame every page is read inside. The header holds the name, three menus
  of the site's pages (`TechtreeWeb.SiteMenu`), the project source, the account
  control with the theme switch, and Book Call; below a wide screen the menus
  fold into one Menu sheet. The footer lists the same pages in columns, with
  the agent links, the legal pages and whose project this is.
  """

  use TechtreeWeb, :html

  alias TechtreeWeb.Components.BookCall
  alias TechtreeWeb.SiteMenu

  embed_templates("layouts/*")

  @repository_url "https://github.com/regents-ai/techtree"
  @buy_regent "https://app.uniswap.org/explore/tokens/base/0x6f89bcA4eA5931EdFCB09786267b251DeE752b07"

  @doc """
  Wrap one page.
  """
  attr(:wide, :boolean, default: false, doc: "give the page the wider measure")
  attr(:flush, :boolean, default: false, doc: "let a page own its vertical rhythm")
  slot(:inner_block, required: true)

  def page(assigns) do
    ~H"""
    <Regent.Structure.row rail={false}>
      <main id="main-content" class={["page", @wide && "page--wide", @flush && "page--flush"]}>
        {render_slot(@inner_block)}
      </main>
    </Regent.Structure.row>

    <.product_links />
    """
  end

  attr(:current_path, :string, default: "/")
  slot(:inner_block, required: true, doc: "the account control, its menu and the theme switch")

  # Each menu is a button and the popover it opens: the browser closes it on
  # Escape or a press outside it, and puts its links next in the Tab order.
  # Below a wide screen the buttons give way to Menu, which opens every group
  # in one sheet under the header (`assets/js/site_menu.ts`).
  defp masthead(assigns) do
    assigns =
      assign(assigns,
        repository_url: @repository_url,
        groups: SiteMenu.groups(),
        github_stars: TechtreeWeb.GithubStars.count()
      )

    ~H"""
    <header class="masthead">
      <div class="masthead__inner">
        <a class="masthead__name" href={~p"/"} aria-label="Techtree home">
          <.mark class="masthead__mark" />
          <span class="masthead__wordmark">Techtree</span>
        </a>
        <nav class="masthead__nav" aria-label="Primary">
          <ul class="masthead__groups">
            <li :for={group <- @groups}>
              <button
                type="button"
                class="masthead__trigger"
                popovertarget={"menu-#{group.id}"}
                data-menu-trigger
              >
                {group.name}
                <Regent.Icons.icon name="chevron-down" class="masthead__chevron" />
              </button>
              <div id={"menu-#{group.id}"} class="mega" popover data-mega>
                <.menu_columns group={group} place="menu" current_path={@current_path} />
              </div>
            </li>
          </ul>
        </nav>
        <div class="masthead__end">
          <a
            class="masthead__github"
            href={@repository_url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={stars_label(@github_stars)}
            title="regents-ai/techtree on GitHub"
          >
            <.github_logo class="masthead__github-logo" />
            <span class="masthead__github-label">Star</span>
            <span :if={@github_stars != :none} class="masthead__github-count">
              <span>{stars_shown(@github_stars)}</span>
              <Regent.Icons.icon name="star" class="masthead__github-star" />
            </span>
          </a>
          {render_slot(@inner_block)}
          <BookCall.book_call class="masthead__book" />
          <button
            type="button"
            class="masthead__menu-button"
            popovertarget="site-menu"
            aria-label="Menu"
          >
            <Regent.Icons.icon name="menu" class="masthead__menu-open" />
            <Regent.Icons.icon name="x" class="masthead__menu-close" />
          </button>
        </div>
      </div>
      <div id="site-menu" class="sheet" popover data-sheet>
        <nav class="sheet__nav" aria-label="Pages">
          <div :for={group <- @groups} class="sheet__group">
            <p class="sheet__title">{group.name}</p>
            <.menu_columns group={group} place="sheet" current_path={@current_path} />
          </div>
          <div class="sheet__end">
            <a href={@repository_url} target="_blank" rel="noopener noreferrer" class="text-link">
              <.github_logo class="sheet__github" /> GitHub
            </a>
            <BookCall.book_call />
          </div>
        </nav>
      </div>
    </header>
    """
  end

  attr :group, :map, required: true
  attr :place, :string, required: true, doc: "menu or sheet, so each list keeps an id of its own"
  attr :current_path, :string, required: true

  defp menu_columns(assigns) do
    ~H"""
    <div class="menu-columns">
      <div :for={column <- @group.columns} class="menu-columns__column">
        <p class="menu-columns__title" id={"#{@place}-#{@group.id}-#{column.id}"}>
          {column.title}
        </p>
        <ul aria-labelledby={"#{@place}-#{@group.id}-#{column.id}"}>
          <li :for={page <- column.pages}>
            <.menu_page page={page} current_path={@current_path} />
          </li>
        </ul>
      </div>
    </div>
    """
  end

  attr :page, :map, required: true
  attr :current_path, :string, required: true

  # A page still to come with no address of its own is named, not linked.
  defp menu_page(%{page: %{href: nil}} = assigns) do
    ~H"""
    <span class="menu-page">
      <Regent.Icons.icon name={@page.icon} class="menu-page__icon" />
      <span class="menu-page__name">
        {@page.name} <span class="menu-page__soon">Soon</span>
      </span>
      <span class="menu-page__line">{@page.line}</span>
    </span>
    """
  end

  defp menu_page(assigns) do
    ~H"""
    <a
      class="menu-page"
      href={@page.href}
      aria-current={if @page.href == @current_path, do: "page"}
    >
      <Regent.Icons.icon name={@page.icon} class="menu-page__icon" />
      <span class="menu-page__name">
        <span :if={@page.by} class="menu-page__by">{@page.by}</span>
        {@page.name} <span :if={@page.soon} class="menu-page__soon">Soon</span>
      </span>
      <span class="menu-page__line">{@page.line}</span>
    </a>
    """
  end

  attr :class, :string, required: true

  # Techtree's mark: thirteen squares, the canopy of a tree.
  defp mark(assigns) do
    ~H"""
    <span class={@class} aria-hidden="true">
      <svg
        viewBox="0 0 58 34"
        xmlns="http://www.w3.org/2000/svg"
        fill="currentColor"
        aria-hidden="true"
      >
        <rect x="0" y="0" width="10" height="10" />
        <rect x="24" y="0" width="10" height="10" />
        <rect x="48" y="0" width="10" height="10" />
        <rect x="0" y="12" width="10" height="10" />
        <rect x="12" y="12" width="10" height="10" />
        <rect x="24" y="12" width="10" height="10" />
        <rect x="36" y="12" width="10" height="10" />
        <rect x="48" y="12" width="10" height="10" />
        <rect x="0" y="24" width="10" height="10" />
        <rect x="12" y="24" width="10" height="10" />
        <rect x="24" y="24" width="10" height="10" />
        <rect x="36" y="24" width="10" height="10" />
        <rect x="48" y="24" width="10" height="10" />
      </svg>
    </span>
    """
  end

  attr :class, :string, required: true

  defp github_logo(assigns) do
    ~H"""
    <svg class={@class} viewBox="0 0 16 16" aria-hidden="true">
      <path d="M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.08-.55-.17-.55-.38 0-.27.01-1.13.01-2.2 0-.75-.25-1.23-.54-1.48 1.78-.2 3.65-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 0-.67-.22-2.2.82-.64.18-1.32.27-2 .27-.68 0-1.36-.09-2-.27-1.53-1.04-2.2-.82-2.2-.82-.44 1.1-.16 1.91-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 3.75 3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55-2.33-.66-.15-.24-.6-.83-1.23-.82-.61.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 1.31 2.69.94 0 .67.01 1.3.01 1.49 0 .21-.15.45-.55.38A8.013 8.013 0 0 1 0 8c0-4.42 3.58-8 8-8Z" />
    </svg>
    """
  end

  defp stars_shown({:ok, count}), do: TechtreeWeb.GithubStars.compact(count)

  defp stars_label({:ok, 1}), do: "regents-ai/techtree on GitHub, 1 star"
  defp stars_label({:ok, count}), do: "regents-ai/techtree on GitHub, #{count} stars"
  defp stars_label(:none), do: "Star on GitHub"

  defp request_path(%{conn: %Plug.Conn{request_path: path}}), do: path
  defp request_path(_assigns), do: "/"

  defp canonical_url(assigns), do: TechtreeWeb.Endpoint.url() <> request_path(assigns)

  defp share_title(title) when title in [nil, ""], do: "Techtree"
  defp share_title(title), do: title <> " · Techtree"

  # A published Result's page shows its own picture (`TechtreeWeb.ResultShareCard`);
  # every other page shows the site's.
  defp share_image(%{share_image: image}), do: image

  defp share_image(_assigns),
    do: %{
      url: url(~p"/images/techtree-share.png"),
      alt: "Techtree: upgrade a Skill, Harness, or Env."
    }

  # Who Techtree is, for a reader that speaks schema.org. There is no postal
  # address: none has been published. `Regent.AgentMetadata.head` encodes it.
  defp structured_data do
    url = TechtreeWeb.Endpoint.url()
    organization = "https://regents.sh/#organization"

    %{
      "@context" => "https://schema.org",
      "@graph" => [
        %{
          "@type" => "WebSite",
          "@id" => url <> "/#website",
          "name" => "Techtree",
          "url" => url,
          "publisher" => %{"@id" => organization}
        },
        %{
          "@type" => "Organization",
          "@id" => organization,
          "name" => "Regents Labs",
          "url" => "https://regents.sh",
          "logo" => "https://regents.sh/mark.png",
          "sameAs" => ["https://github.com/regents-ai"],
          "contactPoint" => %{
            "@type" => "ContactPoint",
            "email" => "build@regents.sh",
            "contactType" => "customer support"
          }
        },
        %{
          "@type" => "SoftwareApplication",
          "@id" => url <> "/#application",
          "name" => "Techtree",
          "url" => url,
          "description" => description_for_path("/"),
          "applicationCategory" => "DeveloperApplication",
          "operatingSystem" => "macOS, Linux",
          "license" => "https://opensource.org/licenses/MIT",
          "offers" => %{"@type" => "Offer", "price" => "0", "priceCurrency" => "USD"},
          "publisher" => %{"@id" => organization}
        },
        %{
          "@type" => "SoftwareSourceCode",
          "name" => "Techtree",
          "codeRepository" => @repository_url,
          "license" => "https://opensource.org/licenses/MIT",
          "targetProduct" => %{"@id" => url <> "/#application"}
        }
      ]
    }
  end

  defp page_description(assigns) do
    assigns
    |> request_path()
    |> description_for_path()
  end

  defp description_for_path("/start"),
    do: "Try the example Climb or evaluate your own Skill."

  defp description_for_path("/results"),
    do: "Browse published Results: the same agent on the same tasks, with and without a Skill."

  defp description_for_path("/verify"),
    do:
      "How a Result is made, what checking one tells you and what it can’t, and how to check one yourself."

  defp description_for_path("/repo2rlenv"),
    do:
      "Repo2RLEnv will turn a repository’s history into practice tasks for agents. Ask to hear when it opens."

  defp description_for_path("/services/verify"),
    do:
      "Techtree Verify: agreed workflow checks, reproducible failures, a suite you can run again and a clear report."

  defp description_for_path("/services/verify/sample-report"),
    do:
      "A sample Techtree Verify report: 14 checks on the Agent Wallet Bench, each with its evidence."

  defp description_for_path("/services/cyber-assist"),
    do:
      "Techtree Cyber Assist: validated security findings, reproduction evidence, repairs in priority order and verified fixes."

  defp description_for_path("/services/cyber-assist/sample-report"),
    do:
      "A sample Techtree Cyber Assist report: one validated finding on the Agent Wallet Bench, fixed, verified and released."

  defp description_for_path("/formal"),
    do:
      "Techtree Formal: what formal verification proves and what it doesn't, recent advances with their sources, and how to send code to be proved."

  defp description_for_path("/services/watchdog"),
    do:
      "Techtree Watchdog: a monthly watch on the sites you own, proven ownership, agreed limits, reproduced findings with fixes and a retest."

  defp description_for_path("/docs"),
    do: "Install Techtree, test a Skill, check and publish a Result, and connect an agent."

  defp description_for_path("/docs/" <> slug) do
    case TechtreeWeb.DocsGuides.fetch(slug) do
      {:ok, guide} -> guide.summary
      :error -> description_for_path("/")
    end
  end

  defp description_for_path("/agents" <> _rest = path),
    do: TechtreeWeb.AgentGuides.description(path) || description_for_path("/")

  defp description_for_path("/changelog"),
    do: "Techtree release notes: new features, fixes, and the limits of each release."

  defp description_for_path("/climbs/" <> _slug),
    do: "Inspect the fixed task contract for a published Techtree Climb."

  defp description_for_path("/about"),
    do:
      "What Techtree is, who runs it and how to reach them, what makes it different, and its key facts."

  defp description_for_path("/privacy"),
    do: "What Techtree keeps about a visitor, what it never sees, and how to ask about either."

  defp description_for_path("/terms"),
    do:
      "The terms for using Techtree: runs, published Results, and what each side is responsible for."

  defp description_for_path("/animations"),
    do: "Every motion Techtree uses, side by side."

  defp description_for_path("/train"),
    do:
      "NVIDIA Nemotron models before and after one change, on the same held-out tasks with the same settings."

  defp description_for_path("/train/" <> _slug),
    do:
      "One NVIDIA Nemotron model before and after one change: mean rewards, task results, settings and evidence."

  defp description_for_path("/results/" <> _digest),
    do: "Inspect one published Techtree Result and its task-level evidence."

  defp description_for_path(_path),
    do: "Improve a Skill under controlled conditions and produce a checkable local Result."

  @doc """
  The footer under every page: the site's pages in columns (the header's
  menus, `TechtreeWeb.SiteMenu`), the files to hand an agent, $REGENT, the
  legal pages and the brand links.
  """
  def product_links(assigns) do
    assigns = assign(assigns, :columns, footer_columns())

    ~H"""
    <Regent.Structure.row rail={false}>
      <footer class="regent-footer">
        <div class="regent-footer__top">
          <div class="regent-footer__brand">
            <a class="regent-footer__name" href={~p"/"}>
              <.mark class="regent-footer__mark" /> Techtree
            </a>
            <p class="regent-footer__line">Improve a Skill. Prove it worked.</p>
            <div class="regent-footer__social">
              <a
                href="https://x.com/regents_sh"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Techtree on X"
              >
                <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
                </svg>
              </a>
              <a
                href="https://github.com/regents-ai"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Techtree on GitHub"
              >
                <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
                </svg>
              </a>
            </div>
          </div>
          <nav class="regent-footer__columns" aria-label="Site">
            <div :for={column <- @columns} class="regent-footer__column">
              <p class="regent-footer__title" id={"footer-#{column.id}"}>{column.title}</p>
              <ul aria-labelledby={"footer-#{column.id}"}>
                <li :for={page <- column.pages}>
                  <a
                    :if={page.href}
                    href={page.href}
                    target={external?(page.href) && "_blank"}
                    rel={external?(page.href) && "noopener noreferrer"}
                  >
                    <span :if={page.by} class="regent-footer__by">{page.by}</span>
                    {page.name}
                  </a>
                  <span :if={!page.href}>{page.name}</span>
                  <span :if={page.soon} class="regent-footer__soon">Soon</span>
                </li>
              </ul>
            </div>
          </nav>
        </div>
        <div class="regent-footer__base">
          <p>© 2026 Regents Labs</p>
          <nav class="regent-footer__legal" aria-label="Legal">
            <a href={~p"/privacy"}>Privacy policy</a>
            <a href={~p"/terms"}>Terms of use</a>
          </nav>
        </div>
        <div class="regent-footer__giant" aria-hidden="true">Techtree</div>
      </footer>
    </Regent.Structure.row>
    """
  end

  # The Products menu's columns as they are; each of the other two menus as one
  # column, $REGENT with the resources, and the Stack on its own.
  defp footer_columns do
    [products, agents, resources] = SiteMenu.groups()
    stack = SiteMenu.stack()
    regent = %{name: "Buy $REGENT", by: nil, href: @buy_regent, soon: false}

    products.columns ++
      [
        %{id: agents.id, title: agents.name, pages: Enum.flat_map(agents.columns, & &1.pages)},
        %{
          id: resources.id,
          title: resources.name,
          pages: Enum.flat_map(resources.columns -- [stack], & &1.pages) ++ [regent]
        },
        stack
      ]
  end

  defp external?(href), do: String.starts_with?(href, "https://")
end
