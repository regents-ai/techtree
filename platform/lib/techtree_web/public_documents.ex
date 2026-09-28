defmodule TechtreeWeb.PublicDocuments do
  @moduledoc """
  The pages Techtree publishes to people and to agents at the same address.

  Each is committed Markdown in `priv/public`, and the changelog is
  `priv/changelog.md`, the same file the Changelog page shows. An agent that
  asks `/`, `/docs`, `/about`, `/contact`, `/privacy`, `/terms` or `/changelog`
  for `text/markdown` receives it with one closing line, answered before the
  router by `RegentAgentAccess.Plug`. About, Contact, Privacy and Terms show the
  same words as pages, so the two never say different things; the home page's
  and the Docs page's own designs are their LiveViews, and their Markdown is the
  same facts in words. The Docs page shows its reference sections from the
  Markdown itself (`docs_section/1`). `/llms.txt` is the agent guide with the
  browser tool table filled in. `robots.txt`, `security.txt` and the API
  catalog are built here too. None of these reads the database.
  """

  @directory Application.app_dir(:techtree, "priv/public")
  @names ~w(home docs about contact privacy terms llms)
  for name <- @names, do: @external_resource(Path.join(@directory, name <> ".md"))
  @changelog_file Application.app_dir(:techtree, "priv/changelog.md")
  @external_resource @changelog_file
  @request_rate_limit Application.compile_env!(:techtree, :request_rate_limit)
  @publication_rate_limit Application.compile_env!(:techtree, [Techtree.Network, :rate_limit])
  @fills %{
    "{{tools}}" => Techtree.Capabilities.markdown_table(),
    "{{request_limit}}" => Integer.to_string(@request_rate_limit[:limit]),
    "{{request_remaining}}" => Integer.to_string(@request_rate_limit[:limit] - 1),
    "{{request_window}}" => Integer.to_string(@request_rate_limit[:window_seconds]),
    "{{publication_limit}}" => Integer.to_string(@publication_rate_limit[:limit]),
    "{{publication_window}}" => Integer.to_string(@publication_rate_limit[:window_seconds])
  }
  # Each `{{name}}` in a source is filled in once, here.
  @sources @names
           |> Map.new(&{&1, File.read!(Path.join(@directory, &1 <> ".md"))})
           |> Map.put("changelog", File.read!(@changelog_file))
           |> Map.new(fn {name, source} ->
             {name,
              Enum.reduce(@fills, source, fn {key, fill}, text ->
                String.replace(text, key, fill)
              end)}
           end)
  @pages %{
    "/about" => "about",
    "/contact" => "contact",
    "/privacy" => "privacy",
    "/terms" => "terms"
  }
  @paths Map.merge(@pages, %{"/" => "home", "/docs" => "docs", "/changelog" => "changelog"})

  @trailer "\n---\n\nTechtree answers `/`, `/docs`, `/about`, `/contact`, `/privacy`, `/terms` " <>
             "and `/changelog` " <>
             "as Markdown when asked with `Accept: text/markdown`. " <>
             "Public API: [/openapi.json](/openapi.json). " <>
             "Agent guide: [/llms.txt](/llms.txt).\n"

  # The public documents change only with a release, so the release time is when
  # each last changed. security.txt expires a year after it.
  @released_at DateTime.utc_now() |> DateTime.truncate(:second)

  @llms @sources["llms"]

  # The Docs page's reference sections, as HTML, by their `##` heading.
  @docs_sections @sources["docs"]
                 |> String.split("\n## ")
                 |> tl()
                 |> Map.new(fn section ->
                   [heading, body] = String.split(section, "\n", parts: 2)
                   {body_html, _contents} = RegentBlog.markdown(body)
                   {heading, body_html}
                 end)

  @doc "The public document at `path` as `%{markdown: text}`, or nil for every other address."
  @spec document(String.t()) :: %{markdown: String.t()} | nil
  def document(path) do
    case @paths do
      %{^path => name} -> %{markdown: @sources[name] <> @trailer}
      _other -> nil
    end
  end

  @doc "The agent guide served at `/llms.txt`."
  @spec llms() :: String.t()
  def llms, do: @llms

  @doc """
  About, Contact, Privacy or Terms split for its page layout: the title, the
  one-paragraph lede under it, and the rest rendered as HTML.
  """
  @spec page(String.t()) :: %{title: String.t(), lede: String.t(), body_html: String.t()}
  for {path, name} <- @pages do
    ["# " <> title, lede, body] = String.split(@sources[name], "\n\n", parts: 3)
    {body_html, _contents} = RegentBlog.markdown(body)

    def page(unquote(path)),
      do: %{title: unquote(title), lede: unquote(lede), body_html: unquote(body_html)}
  end

  @doc "One `##` section of the Docs Markdown, below its heading, as HTML."
  @spec docs_section(String.t()) :: String.t()
  def docs_section(heading), do: Map.fetch!(@docs_sections, heading)

  @doc "When the public documents last changed: the time this release was built."
  @spec released_at() :: DateTime.t()
  def released_at, do: @released_at

  @doc "The crawler rules, naming the sitemap."
  @spec robots() :: String.t()
  def robots, do: "User-agent: *\nAllow: /\n\nSitemap: #{url("/sitemap.xml")}\n"

  @doc "The RFC 9116 security contact file; it expires a year after the release."
  @spec security_txt() :: String.t()
  def security_txt do
    """
    Contact: mailto:build@regents.sh
    Expires: #{@released_at |> DateTime.shift(year: 1) |> DateTime.to_iso8601()}
    Preferred-Languages: en
    Canonical: #{url("/.well-known/security.txt")}
    Policy: #{url("/contact")}
    """
  end

  @doc "The RFC 9727 API catalog: a linkset naming the API, its description and its documentation."
  @spec api_catalog() :: map()
  def api_catalog do
    %{
      "linkset" => [
        %{
          "anchor" => url("/api/v1"),
          "service-desc" => [%{"href" => url("/openapi.json"), "type" => "application/json"}],
          "service-doc" => [%{"href" => url("/docs"), "type" => "text/html"}]
        }
      ]
    }
  end

  @doc "Where a reader that reached a missing or refused address can go instead."
  @spec recovery_links() :: [{String.t(), String.t()}]
  def recovery_links do
    [
      {"Home", url("/")},
      {"Start", url("/start")},
      {"Results", url("/results")},
      {"Docs", url("/docs")},
      {"OpenAPI description", url("/openapi.json")},
      {"Agent guide", url("/llms.txt")},
      {"Sitemap", url("/sitemap.xml")}
    ]
  end

  defp url(path), do: TechtreeWeb.Endpoint.url() <> path
end
