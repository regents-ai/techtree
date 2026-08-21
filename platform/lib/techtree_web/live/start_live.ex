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
     |> assign(page_title: "Install Techtree")
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
      <h1>Install Techtree</h1>
      <p class="lede">
        The pinned installation guide. Two ways in — pick whichever matches who is at the
        keyboard.
      </p>

      <InstallComponents.install focus={@focus} instructions={@instructions} path={~p"/start"} />

      <InstallComponents.requirements instructions={@instructions} />

      <InstallComponents.pinned_commands instructions={@instructions} />

      <InstallComponents.scanning instructions={@instructions} />

      <InstallComponents.disclosure />

      <InstallComponents.hermes_intro />

      <p class="small quiet section">
        Each Climb states what happens to your recordings and to the work you submit.
        <a href={~p"/climbs"}>Read the terms of a Climb</a>
        if you would rather see
        them before you install anything.
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
