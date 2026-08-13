defmodule TechtreeWeb.StartLive do
  @moduledoc """
  The two supported ways to run a Climb on your own machine.

  Every command shown here is built from the installation contract the site
  publishes, never written into the page: what a reader copies is what the
  release says, or the page says plainly that there is nothing to copy yet.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query
  alias TechtreeWeb.ClimbCopy

  @impl true
  def mount(_params, _session, socket) do
    published = instructions()

    {:ok,
     socket
     |> assign(page_title: "Start on your machine")
     |> assign(instructions: published)
     |> assign(copy: ClimbCopy.for_reference(introductory(published)))}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page>
      <h1>Start on your machine</h1>
      <p class="lede">
        Techtree runs where your agent runs. There are two supported ways in.
      </p>

      <.warning_callout
        :if={placeholder?(@instructions)}
        title="These installation details are not a real release yet"
        attention
      >
        <p>
          The versions and revisions below are stand-ins, published so that the path
          can be read and reviewed. They install nothing. When the first release is
          signed off, this page will show its exact versions.
        </p>
      </.warning_callout>

      <p :if={is_nil(@instructions)} class="section">
        Installation details are not published on this site yet.
      </p>

      <div :if={@instructions}>
        <section class="section">
          <h2>Through your agent</h2>
          <p>
            If you already work with Hermes, it can set Techtree up and run the
            introductory Climb for you, asking before each step that costs you
            something.
          </p>

          <ol class="steps">
            <.next_step title="Add the pinned Techtree plugin and enable it.">
              <.command_block argv={plugin_install(@instructions)} />
            </.next_step>
            <.next_step title="Check that the plugin is healthy.">
              <.command_block argv={plugin_doctor(@instructions)} />
            </.next_step>
            <.next_step title="Open Hermes, in a terminal or a connected phone channel." />
            <.next_step title="Ask it, in your own words or these:">
              <p class="digest">{host_prompt(@instructions)}</p>
            </.next_step>
            <.next_step title="Read what it asks you to approve.">
              <p>
                Before anything runs you will be asked to approve the software being
                installed, the rights that apply to your recordings, the machine
                resources a run will use, and the cost of the model calls it makes.
              </p>
            </.next_step>
          </ol>
        </section>

        <section class="section">
          <h2>Straight from the command line</h2>

          <ol class="steps">
            <.next_step title="Install the pinned Techtree command-line tool.">
              <.command_block argv={cli_install(@instructions)} />
            </.next_step>
            <.next_step title="Prepare the machine.">
              <.command_block argv={["techtree", "setup"]} />
              <p class="small quiet">
                This checks what is missing and installs the evaluation engine.
              </p>
            </.next_step>
            <.next_step title="See what is on offer.">
              <.command_block argv={["techtree", "climb", "list"]} />
            </.next_step>
            <.next_step title="Read the introductory Climb, then enter it.">
              <.command_block argv={["techtree", "climb", "show", introductory(@instructions)]} />
              <p :if={@copy} class="small quiet">{@copy.scope}</p>
              <p :if={introductory_slug(@instructions)} class="small">
                <a href={~p"/climbs/#{introductory_slug(@instructions)}"}>
                  What this Climb measures
                </a>
              </p>
            </.next_step>
          </ol>
        </section>

        <section class="section">
          <h2>What the machine needs</h2>
          <.definition_list>
            <:fact term="Docker">
              Running. Each trial runs in a clean container so that the two runs
              being compared start from the same place.
            </:fact>
            <:fact term="A model provider">
              Your own account and key. The agent under test makes real model calls,
              and you pay for them. Techtree never asks for the key.
            </:fact>
            <:fact term="Hermes">
              Version {minimum_hermes(@instructions)} or newer, for the agent path.
            </:fact>
            <:fact term="An operating system">
              macOS or Linux, on Apple silicon or a 64-bit Intel or AMD machine.
            </:fact>
          </.definition_list>
        </section>
      </div>

      <section class="section">
        <h2>Before you enter</h2>
        <p>
          Each Climb states what happens to your recordings and to the work you
          submit, and the command line asks you to accept those terms by name
          before a run starts. <a href={~p"/climbs"}>Read the terms of a Climb</a> first if you would
          rather see them here.
        </p>
      </section>
    </Layouts.page>
    """
  end

  defp instructions do
    case Query.bootstrap_instructions() do
      {:ok, instructions} -> instructions
      {:error, _error} -> nil
    end
  end

  defp placeholder?(nil), do: false
  defp placeholder?(instructions), do: instructions["placeholder_release"] == true

  defp plugin_install(instructions), do: get_in(instructions, ["hermes_plugin", "install_argv"])
  defp plugin_doctor(instructions), do: get_in(instructions, ["hermes_plugin", "doctor_argv"])
  defp cli_install(instructions), do: get_in(instructions, ["cli", "install_argv"])
  defp host_prompt(instructions), do: get_in(instructions, ["introductory_climb", "host_prompt"])
  defp introductory(instructions), do: get_in(instructions, ["introductory_climb", "reference"])
  defp minimum_hermes(instructions), do: get_in(instructions, ["minimums", "hermes_version"])

  defp introductory_slug(instructions) do
    case introductory(instructions) do
      reference when is_binary(reference) -> reference |> String.split("@") |> hd()
      _other -> nil
    end
  end
end
