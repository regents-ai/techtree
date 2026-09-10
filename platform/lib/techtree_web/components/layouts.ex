defmodule TechtreeWeb.Layouts do
  @moduledoc """
  The frame every page is read inside: a name, the primary site sections, the
  project source, a local color control, and one line at the bottom saying whose
  project this is.
  """

  use TechtreeWeb, :html

  embed_templates("layouts/*")

  @repository_url "https://github.com/regents-ai/techtree"

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
  attr(:theme, :string, default: "light")

  defp masthead(assigns) do
    assigns = assign(assigns, :repository_url, @repository_url)

    ~H"""
    <header class="masthead">
      <div class="masthead__inner">
        <a class="masthead__name" href={~p"/"} aria-label="Techtree home">
          <span class="masthead__mark" aria-hidden="true">
            <svg viewBox="0 0 58 34" xmlns="http://www.w3.org/2000/svg" fill="currentColor">
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
          <span>Techtree</span>
        </a>
        <nav class="masthead__nav" aria-label="Primary">
          <span class="masthead__selector">
            <a href={~p"/start"} aria-current={current_section(@current_path, "/start")}>
              Start
            </a>
            <a href={~p"/results"} aria-current={current_section(@current_path, "/results")}>
              Results
            </a>
            <a href={~p"/verify"} aria-current={current_section(@current_path, "/verify")}>
              Verify
            </a>
            <a href={~p"/docs"} aria-current={current_section(@current_path, "/docs")}>Docs</a>
            <a
              class="masthead__service"
              href={~p"/repo2rlenv"}
              aria-current={current_section(@current_path, "/repo2rlenv")}
            >
              Repo2RLEnv Service
            </a>
          </span>
          <a
            class="masthead__github"
            href={@repository_url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Star on GitHub"
            title="regents-ai/techtree on GitHub"
            data-github-stars-link
            data-github-repository="regents-ai/techtree"
          >
            <svg class="masthead__github-logo" viewBox="0 0 16 16" aria-hidden="true">
              <path d="M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.08-.55-.17-.55-.38 0-.27.01-1.13.01-2.2 0-.75-.25-1.23-.54-1.48 1.78-.2 3.65-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 0-.67-.22-2.2.82-.64.18-1.32.27-2 .27-.68 0-1.36-.09-2-.27-1.53-1.04-2.2-.82-2.2-.82-.44 1.1-.16 1.91-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 3.75 3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55-2.33-.66-.15-.24-.6-.83-1.23-.82-.61.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 1.31 2.69.94 0 .67.01 1.3.01 1.49 0 .21-.15.45-.55.38A8.013 8.013 0 0 1 0 8c0-4.42 3.58-8 8-8Z" />
            </svg>
            <span class="masthead__github-label">Star</span>
          </a>
          <a
            class="masthead__github-count"
            href={"#{@repository_url}/stargazers"}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Techtree stargazers on GitHub"
            data-github-stars
            hidden
          ></a>
        </nav>
        <Regent.ThemeToggle.button
          id="site-theme-toggle"
          theme={@theme}
          data-theme-toggle
        />
      </div>
    </header>
    """
  end

  defp masthead_visible?(assigns) do
    case assigns[:conn] do
      %Plug.Conn{request_path: "/prism"} -> false
      _conn -> true
    end
  end

  defp current_section("/proofs", "/verify"), do: "page"

  defp current_section(path, root) when is_binary(path) do
    if path == root or String.starts_with?(path, root <> "/"), do: "page"
  end

  defp request_path(%{conn: %Plug.Conn{request_path: path}}), do: path
  defp request_path(_assigns), do: "/"

  defp page_description(assigns) do
    assigns
    |> request_path()
    |> description_for_path()
  end

  defp description_for_path("/start"),
    do: "Set up Techtree with the CLI or Hermes plugin and run the Hello World Climb."

  defp description_for_path("/results"),
    do: "Browse participant-attested Results from controlled Skill comparisons."

  defp description_for_path(path) when path in ["/proofs", "/verify"],
    do:
      "Understand what Techtree verifies, what remains unproven, and how to check a Result offline."

  defp description_for_path("/repo2rlenv"),
    do:
      "Repo2RLEnv: Techtree’s planned first service for turning repositories into reproducible reinforcement-learning environments."

  defp description_for_path("/docs"),
    do: "Install, operate, verify, publish, and integrate Techtree."

  defp description_for_path("/climbs/" <> _slug),
    do: "Inspect the fixed task contract for a published Techtree Climb."

  defp description_for_path("/results/" <> _digest),
    do: "Inspect one published Techtree Result and its task-level evidence."

  defp description_for_path(_path),
    do: "Improve a Skill under controlled conditions and produce a checkable local Result."

  @doc "Product and source discovery without loading a browser integration."
  def product_links(assigns) do
    ~H"""
    <Regent.Structure.row rail={false}>
      <footer aria-label="Project links" class="product-links">
        <a href="https://github.com/regents-ai/techtree" rel="noopener noreferrer">Star on GitHub</a>
        <a href="/llms.txt">For agents</a>
        <a href={~p"/repo2rlenv"}>Repo2RLEnv · Planned</a>
        <Regent.Primitives.disclosure id="related-products" summary="Regents Labs">
          <nav aria-label="Related products" class="product-links__related">
            <a href="https://regents.sh">Regents</a>
            <a href="https://autolaunch.sh">Autolaunch</a>
            <a href="https://patchbay.help">Patchbay</a>
          </nav>
        </Regent.Primitives.disclosure>
      </footer>
    </Regent.Structure.row>
    """
  end
end
