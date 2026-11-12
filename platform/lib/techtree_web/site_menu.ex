defmodule TechtreeWeb.SiteMenu do
  @moduledoc """
  The site's pages in groups: the header's three menus (`TechtreeWeb.Layouts`)
  open one group each, and the footer lists the same pages in columns.

  Each page is a map with its name, a Lucide icon, one short line, its address
  and whether it is still to come. A page still to come with no address of its
  own yet has `href: nil` and is shown without a link.
  """

  use TechtreeWeb, :verified_routes

  @type page :: %{
          name: String.t(),
          icon: String.t(),
          line: String.t(),
          href: String.t() | nil,
          soon: boolean()
        }
  @type column :: %{id: String.t(), title: String.t(), pages: [page()]}
  @type group :: %{id: String.t(), name: String.t(), columns: [column()]}

  @doc "The header's menus, in the order they sit in the header."
  @spec groups() :: [group()]
  def groups do
    [
      %{
        id: "products",
        name: "Products",
        columns: [
          column("measure", "Measure", [
            page(
              "Skill test",
              "flask-conical",
              "Your agent, with and without a Skill",
              ~p"/start"
            ),
            page(
              "Results",
              "list-checks",
              "Published comparisons anyone can check",
              ~p"/results"
            ),
            page("Wallet Bench", "wallet", "Coding agents setting up wallets", ~p"/wallet-bench"),
            page("Train", "trending-up", "Models before and after one change", ~p"/train")
          ]),
          column("prove", "Prove", [
            page("Offline check", "badge-check", "Check a signed Result yourself", ~p"/verify"),
            page("Formal", "sigma", "What a formal proof can show", ~p"/formal")
          ]),
          column("build", "Build", [
            soon("Repo2RLEnv", "git-branch", "Practice tasks from past fixes", ~p"/repo2rlenv"),
            soon(
              "Repository lab",
              "folder-git-2",
              "Compare agents on your own code",
              ~p"/repo2rlenv"
            ),
            soon("Model Climb", "mountain", "Train your own model privately", nil)
          ]),
          column("services", "Services", [
            page(
              "Verify",
              "shield-check",
              "Checks on the workflows you choose",
              ~p"/services/verify"
            ),
            page(
              "Cyber Assist",
              "scan-search",
              "Validated findings, verified fixes",
              ~p"/services/cyber-assist"
            ),
            page("Watchdog", "radar", "A monthly watch on your sites", ~p"/services/watchdog")
          ])
        ]
      },
      %{
        id: "agents",
        name: "Agents",
        columns: [
          column("connect", "Connect", [
            page("Agents", "bot", "Setup steps for each agent", ~p"/agents"),
            page(
              "Browser agents",
              "app-window",
              "What a browser's agent can do here",
              ~p"/docs/browser-agents"
            ),
            page(
              "Paired agents",
              "plug",
              "Pair an agent with your account",
              ~p"/docs/agents-for-a-person"
            )
          ]),
          column("hand-over", "Hand over", [
            page(
              "Setup steps",
              "file-text",
              "Every step, for your agent to follow",
              ~p"/agents.md"
            ),
            page("Site summary", "book-open", "What Techtree is, in one file", ~p"/llms.txt")
          ]),
          column("build-on", "Build on", [
            page("Public API", "code", "Every address, its errors and limits", ~p"/docs/api"),
            page("Install", "terminal", "The command line, on your computer", ~p"/docs/install")
          ])
        ]
      },
      %{
        id: "resources",
        name: "Resources",
        columns: [
          column("learn", "Learn", [
            page("Docs", "book-open", "Install, test, check and publish", ~p"/docs"),
            page("Proof", "file-check", "What a Result proves, and what not", ~p"/docs/method"),
            page("Roadmap", "compass", "Where Techtree is going", ~p"/docs/where-this-goes")
          ]),
          column("news", "News", [
            page("Changelog", "newspaper", "What changed in each release", ~p"/changelog"),
            page("Blog", "pen-line", "Findings from our own tests", ~p"/blog")
          ]),
          column("company", "Company", [
            page("About", "info", "Who runs Techtree, and how to reach us", ~p"/about")
          ])
        ]
      }
    ]
  end

  defp column(id, title, pages), do: %{id: id, title: title, pages: pages}

  defp page(name, icon, line, href),
    do: %{name: name, icon: icon, line: line, href: href, soon: false}

  defp soon(name, icon, line, href),
    do: %{name: name, icon: icon, line: line, href: href, soon: true}
end
