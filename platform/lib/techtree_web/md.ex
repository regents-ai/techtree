defmodule TechtreeWeb.MD do
  @moduledoc """
  The pages that answer `Accept: text/markdown`: the home page, About,
  Contact and Privacy.

  Each is written once, as Markdown in `priv/pages`. A Markdown reader gets
  that text with one closing line; About, Contact and Privacy are also shown
  as pages, rendered from the same text, so the two never say different
  things. The home page's own design is its LiveView; its Markdown is the same
  facts in words.
  """

  import Plug.Conn

  @root Path.expand("../../priv/pages", __DIR__)
  @names [:home, :about, :contact, :privacy]

  for name <- @names, do: @external_resource(Path.join(@root, "#{name}.md"))

  @sources Map.new(@names, &{&1, File.read!(Path.join(@root, "#{&1}.md"))})

  @trailer "\n---\n\nTechtree answers `/`, `/about`, `/contact` and `/privacy` as Markdown " <>
             "when asked with `Accept: text/markdown`. Public API: [/openapi.json](/openapi.json). " <>
             "Agent guide: [/llms.txt](/llms.txt).\n"

  @typedoc "A page that has a Markdown answer."
  @type name :: :home | :about | :contact | :privacy

  @doc "The line every Markdown answer ends with."
  @spec trailer() :: String.t()
  def trailer, do: @trailer

  @doc "One page as the Markdown document it answers with."
  @spec document(name()) :: String.t()
  def document(name), do: Map.fetch!(@sources, name) <> @trailer

  @doc "Answer with one page's Markdown and stop."
  @spec answer(Plug.Conn.t(), name()) :: Plug.Conn.t()
  def answer(conn, name) do
    conn
    |> put_resp_content_type("text/markdown")
    |> send_resp(200, document(name))
    |> halt()
  end

  @doc """
  One page split for its HTML layout: the title, the one-paragraph lede under
  it, and the rest rendered as HTML.
  """
  @spec page(:about | :contact | :privacy) :: %{
          title: String.t(),
          lede: String.t(),
          body_html: String.t()
        }
  for name <- [:about, :contact, :privacy] do
    ["# " <> title, lede, body] = String.split(Map.fetch!(@sources, name), "\n\n", parts: 3)
    {body_html, _contents} = RegentBlog.markdown(body)

    def page(unquote(name)) do
      %{title: unquote(title), lede: unquote(lede), body_html: unquote(body_html)}
    end
  end
end
