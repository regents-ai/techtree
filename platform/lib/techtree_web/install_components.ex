defmodule TechtreeWeb.InstallComponents do
  @moduledoc """
  Getting Techtree installed, which is the only thing this site is for.

  There are two ways in — a person at a terminal, or the agent they already
  work with — and one of them is on screen at a time. Showing both at once
  makes a reader choose before they know what they are choosing between; a
  switcher lets them look at one, then the other.

  Which one is showing is part of the address, so the choice can be sent to
  someone else in a link and so a page that loads without a live connection
  still switches.

  No command here is written into the page. Every one of them comes from the
  installation contract this site publishes, and when that contract says its
  coordinates are stand-ins, the page says so above them.
  """

  use TechtreeWeb, :html

  alias TechtreeWeb.ClimbCopy

  @options [agent: "My agent is installing", me: "I’m installing"]

  @doc """
  Which way in the address asks for.

  Anything the address does not name is the agent path: it is the shorter of
  the two, and the one this release is written around.
  """
  @spec focus(map()) :: :agent | :me
  def focus(%{"install" => "me"}), do: :me
  def focus(_params), do: :agent

  @doc """
  The two ways in, with one of them open.
  """
  attr :focus, :atom, required: true
  attr :instructions, :map, default: nil
  attr :path, :string, required: true, doc: "the page the switcher returns to"

  def install(assigns) do
    assigns = assign(assigns, :climb, ClimbCopy.for_reference(introductory(assigns.instructions)))

    ~H"""
    <.warning_callout
      :if={placeholder?(@instructions)}
      title="This is not a real release yet"
      attention
    >
      <p>
        The versions and revisions below are stand-ins, published so the path can be
        read before it is real. They install nothing.
      </p>
    </.warning_callout>

    <p :if={is_nil(@instructions)} class="section">
      Installation details are not published on this site yet.
    </p>

    <div :if={@instructions}>
      <nav class="actions section" aria-label="Who is installing">
        <.link
          :for={{option, label} <- options()}
          patch={switch_href(@path, option)}
          class={["action", @focus == option && "action--primary"]}
          aria-current={@focus == option && "true"}
        >
          {label}
        </.link>
      </nav>

      <ol class="steps">
        <%= if @focus == :agent do %>
          <.next_step title="Add the Techtree plugin to Hermes.">
            <.command_block argv={plugin_install(@instructions)} />
            <.command_block argv={plugin_doctor(@instructions)} label="Check it worked" />
          </.next_step>
          <.next_step title="Ask your agent, in your own words or these.">
            <p class="digest">{host_prompt(@instructions)}</p>
            <p>
              It asks before it installs anything, runs anything, or spends anything.
            </p>
          </.next_step>
        <% else %>
          <.next_step title="Install the command-line tool.">
            <.command_block argv={cli_install(@instructions)} />
          </.next_step>
          <.next_step title="Prepare the machine.">
            <.command_block argv={["techtree", "setup"]} />
          </.next_step>
          <.next_step title="Read the introductory Climb, then enter it.">
            <.command_block argv={["techtree", "climb", "show", introductory(@instructions)]} />
            <p>
              You are asked to accept the terms of the Climb by name before a run starts.
            </p>
          </.next_step>
        <% end %>
      </ol>

      <p :if={@climb} class="small quiet">{@climb.scope}</p>

      <p :if={introductory_slug(@instructions)} class="small">
        <a href={"/climbs/" <> introductory_slug(@instructions)}>What this Climb measures</a>
      </p>

      <p class="small quiet">
        You need Docker running, macOS or Linux, Hermes {minimum_hermes(@instructions)} or newer,
        and a key from your model provider. The agent under test makes real model calls, and
        those go to that provider under its policies; you pay for them, and Techtree never asks
        for the key. If you later take the guided revision of your Skill, that one request
        carries your Skill text and a sanitized summary of the run to the provider your own
        agent uses.
      </p>
    </div>
    """
  end

  # -- Internals ------------------------------------------------------------

  defp options, do: @options

  defp switch_href(path, option), do: path <> "?install=" <> Atom.to_string(option)

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
