defmodule TechtreeWeb.DocsGuides do
  @moduledoc """
  The Docs guides, in reading order. Each guide has its own page at
  `/docs/<slug>` and its own Markdown in `priv/public/docs/<slug>.md`; the
  `/docs` page and its Markdown list them from here.
  """

  @guides [
    %{
      slug: "install",
      group: "Get started",
      title: "Install and check",
      summary: "Install the release Techtree names and check this machine."
    },
    %{
      slug: "test-a-skill",
      group: "Get started",
      title: "Test your Skill",
      summary: "Make tasks from a Skill, then run them without it and with it."
    },
    %{
      slug: "hello-world",
      group: "Get started",
      title: "Hello World Climb",
      summary: "A small, fixed comparison that shows how a run works."
    },
    %{
      slug: "frontier-cs",
      group: "Get started",
      title: "Frontier-CS problems",
      summary: "Improve a Skill on ten open-ended programming problems."
    },
    %{
      slug: "hermes",
      group: "Get started",
      title: "Use Hermes",
      summary: "Let Hermes run each step, with your yes before every model call."
    },
    %{
      slug: "verify",
      group: "Results",
      title: "Check a Result",
      summary: "Check a Result's evidence on your own computer."
    },
    %{
      slug: "publish",
      group: "Results",
      title: "Publish a Result",
      summary: "Add a finished run to the public Results, or withdraw it."
    },
    %{
      slug: "api",
      group: "For agents",
      title: "Public API",
      summary: "Every address, its errors and limits, and how changes are announced."
    },
    %{
      slug: "browser-agents",
      group: "For agents",
      title: "Browser agents",
      summary: "What a browser's agent can read and do on Techtree."
    },
    %{
      slug: "agents-for-a-person",
      group: "For agents",
      title: "Agents for a person",
      summary: "Pair an agent with your account, and what it can then read."
    },
    %{
      slug: "method",
      group: "How it works",
      title: "How a Result is proved",
      summary: "The comparison, the proof bundle, and what a Result does not prove."
    },
    %{
      slug: "where-this-goes",
      group: "How it works",
      title: "Where this goes",
      summary: "Harnesses, environments and the network around Techtree."
    },
    %{
      slug: "data",
      group: "Help",
      title: "What leaves your machine",
      summary: "What stays on your computer and what Techtree receives."
    },
    %{
      slug: "troubleshooting",
      group: "Help",
      title: "When something goes wrong",
      summary: "Where to look when a step fails."
    }
  ]

  @by_slug Map.new(@guides, &{&1.slug, &1})

  @lede "Install the release, test a Skill against no Skill or its earlier version, check a " <>
          "Result, and publish one to the public Results. Reading the catalog and Results " <>
          "needs no account."

  @type guide :: %{slug: String.t(), group: String.t(), title: String.t(), summary: String.t()}

  @doc "The line under the `/docs` heading."
  @spec lede() :: String.t()
  def lede, do: @lede

  @spec all() :: [guide()]
  def all, do: @guides

  @spec slugs() :: [String.t()]
  def slugs, do: Enum.map(@guides, & &1.slug)

  @spec fetch(String.t()) :: {:ok, guide()} | :error
  def fetch(slug), do: Map.fetch(@by_slug, slug)

  @doc "The guides grouped for the menu, groups in reading order."
  @spec groups() :: [{String.t(), [guide()]}]
  def groups, do: Enum.chunk_by(@guides, & &1.group) |> Enum.map(&{hd(&1).group, &1})

  @doc "The guides just before and after `slug`, or nil at either end."
  @spec neighbours(String.t()) :: {guide() | nil, guide() | nil}
  def neighbours(slug) do
    index = Enum.find_index(@guides, &(&1.slug == slug))
    {if(index > 0, do: Enum.at(@guides, index - 1)), Enum.at(@guides, index + 1)}
  end

  @doc "The `/docs` page as Markdown: every guide, by group, with its link."
  @spec index_markdown() :: String.t()
  def index_markdown do
    groups =
      Enum.map_join(groups(), "\n\n", fn {group, guides} ->
        "## #{group}\n\n" <>
          Enum.map_join(guides, "\n", &"- [#{&1.title}](/docs/#{&1.slug}): #{&1.summary}")
      end)

    "# Docs\n\n#{@lede}\n\n#{groups}\n"
  end
end
