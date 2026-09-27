defmodule TechtreeWeb.PublicDocuments do
  @moduledoc """
  The pages Techtree publishes to people and to agents at the same address.

  Each is committed Markdown in `priv/public`, and the changelog is
  `priv/changelog.md`, the same file the Changelog page shows. An agent that
  asks `/`, `/about`, `/contact`, `/privacy` or `/changelog` for `text/markdown`
  receives it with one closing line, answered before the router by
  `RegentAgentAccess.Plug`. About, Contact
  and Privacy show the same words as pages, so the two never say different
  things; the home page's own design is its LiveView, and its Markdown is the
  same facts in words. `/llms.txt` is the agent guide with the browser tool
  table filled in. None of these reads the database.
  """

  @directory Application.app_dir(:techtree, "priv/public")
  @names ~w(home about contact privacy llms)
  for name <- @names, do: @external_resource(Path.join(@directory, name <> ".md"))
  @changelog_file Application.app_dir(:techtree, "priv/changelog.md")
  @external_resource @changelog_file
  @sources @names
           |> Map.new(&{&1, File.read!(Path.join(@directory, &1 <> ".md"))})
           |> Map.put("changelog", File.read!(@changelog_file))
  @pages %{"/about" => "about", "/contact" => "contact", "/privacy" => "privacy"}
  @paths Map.merge(@pages, %{"/" => "home", "/changelog" => "changelog"})

  @trailer "\n---\n\nTechtree answers `/`, `/about`, `/contact`, `/privacy` and `/changelog` " <>
             "as Markdown when asked with `Accept: text/markdown`. " <>
             "Public API: [/openapi.json](/openapi.json). " <>
             "Agent guide: [/llms.txt](/llms.txt).\n"

  @llms String.replace(@sources["llms"], "{{tools}}", Techtree.Capabilities.markdown_table())

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
  About, Contact or Privacy split for its page layout: the title, the
  one-paragraph lede under it, and the rest rendered as HTML.
  """
  @spec page(String.t()) :: %{title: String.t(), lede: String.t(), body_html: String.t()}
  for {path, name} <- @pages do
    ["# " <> title, lede, body] = String.split(@sources[name], "\n\n", parts: 3)
    {body_html, _contents} = RegentBlog.markdown(body)

    def page(unquote(path)),
      do: %{title: unquote(title), lede: unquote(lede), body_html: unquote(body_html)}
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
