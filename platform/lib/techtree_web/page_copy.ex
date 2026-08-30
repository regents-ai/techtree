defmodule TechtreeWeb.PageCopy do
  @moduledoc """
  The split control that hands a reader the whole page as Markdown.

  Founder ruling 2026-08-26, after the Devin docs reference: one primary
  action copies the page as Markdown for an agent's context window, and a
  small menu repeats it beside "View as Markdown". Everything happens in the
  reader's browser — the Markdown is serialized from the rendered page itself
  (assets/js/app.js), so it can never drift from what the page says, and
  nothing is requested from or sent to the server.
  """

  use Phoenix.Component

  @doc "The Copy page split button. Place inside a page heading."
  def page_copy(assigns) do
    ~H"""
    <div class="pagecopy" data-markdown-skip>
      <button
        type="button"
        class="pagecopy__main"
        id="copy-page"
        phx-hook="CopyCommandPage"
        phx-update="ignore"
      >
        <span data-copy-label>Copy page</span>
      </button>
      <details>
        <summary aria-label="More ways to take this page">⌄</summary>
        <div class="pagecopy__menu">
          <button
            type="button"
            class="pagecopy__item"
            id="copy-page-menu"
            phx-hook="CopyCommandPage"
            phx-update="ignore"
          >
            <span data-copy-label>Copy page</span>
            <small>Copy page as Markdown for agents</small>
          </button>
          <button
            type="button"
            class="pagecopy__item"
            id="view-page-markdown"
            phx-hook="CopyCommandPageView"
            phx-update="ignore"
          >
            View as Markdown <small>Open this page as plain text</small>
          </button>
        </div>
      </details>
    </div>
    """
  end
end
