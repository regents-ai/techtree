defmodule TechtreeWeb.StartLive do
  @moduledoc """
  Installing Techtree, and the one thing to read before entering a Climb.

  Every command shown here is built from the installation contract the site
  publishes, never written into the page: what a reader copies is what the
  release says, or the page says plainly that there is nothing to copy yet.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query
  alias TechtreeWeb.InstallComponents

  @impl true
  def mount(_params, _session, socket) do
    {:ok,
     socket
     |> assign(page_title: "Install Techtree and complete your first Result")
     |> assign(instructions: instructions())}
  end

  @impl true
  def handle_params(params, _uri, socket) do
    {:noreply, assign(socket, focus: InstallComponents.focus(params))}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page>
      <h1>Install Techtree and complete your first Result</h1>
      <p class="lede">
        Pick the agent-guided or direct CLI path. Both end with Doctor printing the exact
        command for the Hello World Climb.
      </p>

      <InstallComponents.install focus={@focus} instructions={@instructions} path={~p"/start"} />

      <InstallComponents.requirements instructions={@instructions} />

      <InstallComponents.pinned_commands instructions={@instructions} />

      <InstallComponents.scanning instructions={@instructions} />

      <InstallComponents.disclosure />

      <InstallComponents.hermes_intro />

      <p class="small quiet section">
        After setup, <a href={~p"/climbs"}>read the Climb contract</a>
        or <a href={~p"/results"}>browse completed Results</a>.
      </p>
    </Layouts.page>
    """
  end

  defp instructions do
    case Query.bootstrap_instructions() do
      {:ok, instructions} -> instructions
      {:error, _error} -> nil
    end
  end
end
