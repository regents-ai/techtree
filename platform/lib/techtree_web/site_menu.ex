defmodule TechtreeWeb.SiteMenu do
  @moduledoc """
  The site's pages for the header and the footer (`TechtreeWeb.Layouts`).

  The header has one menu, Services: the four services
  (`TechtreeWeb.Services`) with Security set apart beside them, each with a
  Lucide icon and one short line. Results and Docs are plain links beside it.
  The footer lists the services, the site's other pages and the files to hand
  an agent, in columns, by name.
  """

  use TechtreeWeb, :verified_routes

  alias TechtreeWeb.Services

  @buy_regent "https://app.uniswap.org/explore/tokens/base/0x6f89bcA4eA5931EdFCB09786267b251DeE752b07"

  @type page :: %{name: String.t(), icon: String.t(), line: String.t(), href: String.t()}
  @type link :: %{name: String.t(), href: String.t()}
  @type column(entry) :: %{id: String.t(), title: String.t(), pages: [entry]}

  @doc "The Services menu: the four services, then Security on its own."
  @spec services() :: [column(page())]
  def services do
    [
      column("services", "Services", Enum.map(Services.all(), &service/1)),
      column("also", "Also", [service(Services.security())])
    ]
  end

  @doc "The header's plain links beside the Services menu, by name and address."
  @spec links() :: [link()]
  def links, do: [link("Results", ~p"/results"), link("Docs", ~p"/docs")]

  @doc "The footer's columns, each page by name and address."
  @spec footer() :: [column(link())]
  def footer do
    [
      column(
        "services",
        "Services",
        for(
          service <- Services.all() ++ [Services.security()],
          do: link(service.name, Services.path(service.id))
        )
      ),
      column("site", "Site", [
        link("Results", ~p"/results"),
        link("Docs", ~p"/docs"),
        link("Run locally", ~p"/docs/run-locally"),
        link("Changelog", ~p"/changelog"),
        link("Blog", ~p"/blog"),
        link("About", ~p"/about"),
        link("Buy $REGENT", @buy_regent)
      ]),
      column("agents", "Agents", [
        link("Agents", ~p"/agents"),
        link("agents.md", ~p"/agents.md"),
        link("llms.txt", ~p"/llms.txt"),
        link("capabilities.json", ~p"/capabilities.json"),
        link("openapi.json", ~p"/openapi.json"),
        link("Public API", ~p"/docs/api"),
        link("Browser agents", ~p"/docs/browser-agents")
      ])
    ]
  end

  defp service(service),
    do: %{
      name: service.name,
      icon: service.icon,
      line: service.line,
      href: Services.path(service.id)
    }

  defp column(id, title, pages), do: %{id: id, title: title, pages: pages}

  defp link(name, href), do: %{name: name, href: href}
end
