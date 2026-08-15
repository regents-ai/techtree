defmodule TechtreeWeb.HomeLive do
  @moduledoc """
  What Techtree Climb is and how to install it, in that order and briefly.

  A reader arriving here wants one of two things: to know within a sentence
  whether this is for them, and then to get it running. Everything else on this
  site is a page away, and nothing on this one changes: no counters, no
  activity, no claims about how many people have run anything.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query
  alias TechtreeWeb.InstallComponents

  @impl true
  def mount(_params, _session, socket) do
    {:ok,
     socket
     |> assign(page_title: "Install Techtree and run a trial")
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
      <h1>Techtree Climb</h1>
      <p class="lede">
        Test one change to an agent on your own machine, and get a result anyone
        can check.
      </p>

      <InstallComponents.install focus={@focus} instructions={@instructions} path={~p"/"} />

      <p :if={@instructions} class="small">
        <a href={~p"/start"}>The full installation guide</a>
        — what the machine needs, what a trial costs, and every command this release pins.
      </p>

      <InstallComponents.disclosure />

      <InstallComponents.hermes_intro />

      <section class="section">
        <h2>What it does</h2>
        <p>
          The same tasks are run twice under the same conditions: once as the agent
          is, and once with your change in place. Everything else is held fixed and
          recorded, so the difference in score has one thing left to be caused by.
        </p>
        <p>
          The result is signed on the machine that produced it and can be checked
          there, offline, by anyone you give it to. It has not been independently
          reproduced, and this site never receives it. <a href={~p"/proofs/local"}>What a local result claims</a>.
        </p>
      </section>

      <p class="small quiet">
        <a href={~p"/climbs"}>The Climbs on offer</a>
        · <a href={~p"/protocol"}>The documents behind them</a>
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
