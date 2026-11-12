defmodule TechtreeWeb.ChangelogLive do
  @moduledoc "Release notes compiled from the repository's canonical changelog."
  use TechtreeWeb, :live_view

  import TechtreeWeb.Components.Marketing, only: [opening: 1]

  @external_resource Path.expand("../../../priv/changelog.md", __DIR__)
  @html @external_resource
        |> File.read!()
        |> String.replace_prefix("# Changelog\n", "")
        |> RegentBlog.markdown()
        |> elem(0)

  @impl true
  def mount(_params, _session, socket) do
    {:ok, assign(socket, page_title: "Changelog", changelog_html: @html)}
  end

  @impl true
  # @html is rendered from the committed changelog at compile time, never request data.
  # sobelow_skip ["XSS.Raw"]
  def render(assigns) do
    ~H"""
    <Layouts.page wide flush>
      <.opening
        eyebrow="News"
        title="Changelog"
        line="What changed, what you can use, and what comes next."
        shape={5}
        icon="newspaper"
      >
        <:actions>
          <.link navigate={~p"/docs/install"} class="rg-button rg-button--primary">Install</.link>
        </:actions>
      </.opening>
      <section class="mk-section">
        <article id="changelog" class="rg-blog__prose" aria-label="Release history">
          {raw(@changelog_html)}
        </article>
      </section>
    </Layouts.page>
    """
  end
end
