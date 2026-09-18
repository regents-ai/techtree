defmodule TechtreeWeb.ChangelogLive do
  @moduledoc "Release notes compiled from the repository's canonical changelog."
  use TechtreeWeb, :live_view

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
  def render(assigns) do
    ~H"""
    <Layouts.page>
      <header class="editorial-heading">
        <p class="eyebrow">Release notes</p>
        <h1>Changelog</h1>
        <p class="lede">What changed, what you can use, and what comes next.</p>
      </header>
      <article id="changelog" class="rg-blog__prose" aria-label="Release history">
        {raw(@changelog_html)}
      </article>
    </Layouts.page>
    """
  end
end
