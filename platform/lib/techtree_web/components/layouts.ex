defmodule TechtreeWeb.Layouts do
  @moduledoc """
  The frame every page is read inside: a name, the primary site sections, the
  project source, a local color control, and one line at the bottom saying whose
  project this is.
  """

  use TechtreeWeb, :html

  embed_templates "layouts/*"

  @repository_url "https://github.com/regents-ai/techtree"
  @repository_stars 0

  @doc """
  Wrap one page.
  """
  attr :wide, :boolean, default: false, doc: "give the page the wider measure"
  attr :flush, :boolean, default: false, doc: "let a page own its vertical rhythm"
  slot :inner_block, required: true

  def page(assigns) do
    ~H"""
    <main class={["page", @wide && "page--wide", @flush && "page--flush"]}>
      <p class="notice" role="status" data-markdown-skip>
        The connection to the site dropped. The page will reconnect on its own.
      </p>
      {render_slot(@inner_block)}
    </main>

    <footer class="colophon">
      <span class="colophon__mark" aria-hidden="true"></span>
      <a href="https://regents.sh" rel="noopener noreferrer">A Regents Labs project</a>
    </footer>
    """
  end

  attr :current_path, :string, default: "/"

  defp masthead(assigns) do
    assigns =
      assign(assigns,
        repository_url: @repository_url,
        repository_stars: @repository_stars
      )

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
            <a href={~p"/results"} aria-current={current_section(@current_path, "/results")}>
              Results
            </a>
            <a href={~p"/proofs"} aria-current={current_section(@current_path, "/proofs")}>
              Proofs
            </a>
            <a href={~p"/docs"} aria-current={current_section(@current_path, "/docs")}>Docs</a>
          </span>
          <a
            class="masthead__github"
            href={@repository_url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={"regents-ai/techtree on GitHub, #{@repository_stars} stars"}
            title="regents-ai/techtree on GitHub"
          >
            <svg class="masthead__github-mark" viewBox="0 0 16 16" aria-hidden="true">
              <path d="M8 0C3.58 0 0 3.64 0 8.13c0 3.59 2.29 6.64 5.47 7.72.4.08.55-.18.55-.39 0-.19-.01-.83-.01-1.51-2.01.38-2.53-.5-2.69-.96-.09-.23-.48-.96-.82-1.15-.28-.15-.68-.53-.01-.54.63-.01 1.08.59 1.23.83.72 1.23 1.87.88 2.33.67.07-.53.28-.88.51-1.08-1.78-.21-3.64-.91-3.64-4.02 0-.89.31-1.62.82-2.19-.08-.2-.36-1.04.08-2.16 0 0 .67-.22 2.2.84A7.4 7.4 0 0 1 8 3.89c.68 0 1.36.09 2 .27 1.53-1.06 2.2-.84 2.2-.84.44 1.12.16 1.96.08 2.16.51.57.82 1.3.82 2.19 0 3.12-1.87 3.81-3.65 4.02.29.25.54.74.54 1.5 0 1.08-.01 1.95-.01 2.22 0 .22.15.47.55.39A8.14 8.14 0 0 0 16 8.13C16 3.64 12.42 0 8 0Z" />
            </svg>
            <span class="masthead__github-count">{@repository_stars}</span>
            <svg class="masthead__github-star" viewBox="0 0 16 16" aria-hidden="true">
              <path d="M8 1.15 9.9 5l4.25.62-3.08 3 .73 4.23L8 10.86l-3.8 2 .73-4.23-3.08-3L6.1 5 8 1.15Z" />
            </svg>
          </a>
        </nav>
        <button
          id="site-theme-toggle"
          class="theme-toggle"
          type="button"
          aria-label="Color theme: Titanium. Activate Orange light theme."
          aria-pressed="false"
          title="Switch color theme"
          data-theme-toggle
        >
          <span class="theme-toggle__stage" aria-hidden="true">
            <span class="theme-toggle__laser"></span>
            <span class="theme-toggle__cube">
              <span class="theme-toggle__face theme-toggle__face--front"></span>
              <span class="theme-toggle__face theme-toggle__face--back"></span>
              <span class="theme-toggle__face theme-toggle__face--left"></span>
              <span class="theme-toggle__face theme-toggle__face--right"></span>
              <span class="theme-toggle__face theme-toggle__face--top"></span>
              <span class="theme-toggle__face theme-toggle__face--bottom"></span>
            </span>
          </span>
          <span class="offscreen" data-theme-toggle-state>Titanium theme active</span>
        </button>
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

  defp current_section(path, root) when is_binary(path) do
    if path == root or String.starts_with?(path, root <> "/"), do: "page"
  end

  defp request_path(%{conn: %Plug.Conn{request_path: path}}), do: path
  defp request_path(_assigns), do: "/"
end
