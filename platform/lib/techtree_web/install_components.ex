defmodule TechtreeWeb.InstallComponents do
  @moduledoc """
  Getting Techtree installed, which is the only thing this site is for.

  There are two ways in — the agent someone already works with, or the person
  at the terminal — and one of them is on screen at a time. Showing both at
  once makes a reader choose before they know what they are choosing between; a
  switcher lets them look at one, then the other.

  Which one is showing is part of the address, so the choice can be sent to
  someone else in a link and so a page that loads without a live connection
  still switches.

  No command here is written into the page. Every one of them comes from the
  installation contract this site publishes, and when that contract says its
  coordinates are stand-ins, the page says so above them. The address of the
  pinned plugin is held to the same rule: it is shown only once the contract
  names a real revision, and never as a branch or a stand-in.

  One thing here is not a command and still has to be said: Hermes reads the
  plugin's source before installing it, and what it reports is not nothing. A
  reader who meets that report for the first time at the moment of installing
  has to decide in a hurry, which is the worst moment to decide anything. So
  the page says beforehand what the report will say, in the same plain words,
  and says that the answer is theirs to give.
  """

  use TechtreeWeb, :html

  alias TechtreeWeb.ClimbCopy

  @options [agent: "My agent is installing", me: "I’m installing"]

  @guide_url "https://techtree.sh/start"
  @portal_url "https://portal.nousresearch.com/"
  @unset_revision String.duplicate("0", 40)

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

      <%= if @focus == :agent do %>
        <.agent_prompt_block instructions={@instructions} />
      <% else %>
        <section class="section">
          <h2>Prefer installing it yourself?</h2>
          <ol class="steps">
            <li>
              <p class="plain">Install the exact pinned Hermes plugin shown below.</p>
            </li>
            <li>
              <p class="plain">Restart Hermes.</p>
            </li>
            <li>
              <p class="plain">Ask: “{host_prompt(@instructions)}”</p>
            </li>
          </ol>
          <.command_block argv={plugin_install(@instructions)} />
          <.command_block argv={plugin_doctor(@instructions)} label="Check it worked" />
          <p class="small quiet">
            Installing a plugin takes your explicit approval, so an agent cannot put
            itself in a position to run trials.
          </p>
        </section>
      <% end %>

      <p :if={@climb} class="small quiet">{@climb.scope}</p>

      <p :if={introductory_slug(@instructions)} class="small">
        <a href={"/climbs/" <> introductory_slug(@instructions)}>What this Climb measures</a>
      </p>
    </div>
    """
  end

  @doc """
  The words a reader hands to their agent.

  Written once and shown wherever the agent path is offered, so that the
  documentation and the installation guide cannot drift into two prompts.
  """
  attr :instructions, :map, default: nil

  def agent_prompt_block(assigns) do
    ~H"""
    <section :if={@instructions} class="section">
      <h2>Give this to your Hermes agent</h2>
      <div class="prompt">
        <pre class="prompt__block"><code>{agent_prompt(@instructions)}</code></pre>
      </div>
      <p class="small quiet">
        It asks before it installs anything, runs anything, or spends anything. A
        trial takes a while, so it hands back a run identifier instead of making you
        wait, and you ask it for the result when you want it.
      </p>
    </section>
    """
  end

  @doc """
  What the machine needs before either path, and what a trial costs.
  """
  attr :instructions, :map, default: nil

  def requirements(assigns) do
    ~H"""
    <section :if={@instructions} class="section">
      <h2>Before you start</h2>

      <.definition_list>
        <:fact term="Operating system">macOS or Linux.</:fact>
        <:fact term="Hermes">
          {minimum(@instructions, "hermes_version")} or newer, already installed and working.
        </:fact>
        <:fact term="Python">
          Nothing to install yourself — the installer provides its own
          Python {minimum(@instructions, "python")}, whatever this machine has.
        </:fact>
        <:fact term="uv">{minimum(@instructions, "uv")} or newer.</:fact>
        <:fact :if={docker_required?(@instructions)} term="Docker">
          Installed, and running before a trial starts.
        </:fact>
        <:fact term="A terminal">
          Techtree installs and runs on the machine in front of you, at a terminal.
        </:fact>
        <:fact term="Model provider">
          An account and a key from your model provider. Techtree never asks for the key.
        </:fact>
      </.definition_list>

      <h2 class="section">What a trial costs</h2>
      <p>
        A trial runs the same tasks twice and spends model tokens on inference both
        times. Those tokens go to the model provider you configured, and where that
        provider charges for them they are billed to the provider account you use; a
        model you run on your own hardware sends no bill. Techtree charges nothing
        and holds no balance.
      </p>
      <p>
        Nothing causing LLM token spend starts on its own. Before each run you are
        shown how many tasks will run, the most that run may cost, and exactly what is
        changing, and it waits for you to say yes. The introductory Climb is small on
        purpose.
      </p>
    </section>
    """
  end

  @doc """
  The one line a reader hands to an agent they already run. Single source —
  the homepage block and the docs quickstart both read it from here.
  """
  def agent_line, do: "Go to techtree.sh/start and set up Techtree and run the Hello World Climb."

  @doc """
  The commands this release pins, taken from the published contract.
  """
  attr :instructions, :map, default: nil

  def pinned_commands(assigns) do
    assigns = assign(assigns, :release_url, pinned_repository_url(assigns.instructions))

    ~H"""
    <section :if={@instructions} class="section">
      <h2>The commands this release pins</h2>
      <p>
        These are the exact commands, argument for argument. Nothing here is typed into
        this page: it is read from the installation contract this site publishes, and it
        changes only when a new release does.
      </p>

      <.command_block
        argv={plugin_install(@instructions)}
        label="Install and enable the Hermes plugin"
      />
      <.command_block
        argv={plugin_doctor(@instructions)}
        label="Check the plugin is loaded"
      />
      <.command_block
        argv={cli_install(@instructions)}
        label="Install the Techtree command-line tool"
      />

      <p class="small quiet">
        Once the plugin is enabled, Hermes has to be restarted once so its Techtree tools
        are loaded. The plugin then installs and checks the command-line tool for you —
        the third command is the one it runs — and asks you before it does.
      </p>

      <p :if={@release_url} class="small">
        <a href={@release_url}>The pinned plugin release on GitHub</a>
      </p>
      <p :if={is_nil(@release_url)} class="small quiet">
        This release does not name a published plugin revision yet, so there is no
        release page to link to.
      </p>
    </section>
    """
  end

  @doc """
  What the install-time scan reports, before a reader meets it.
  """
  attr :instructions, :map, default: nil

  def scanning(assigns) do
    ~H"""
    <section :if={@instructions} class="section">
      <h2>What the security scan will say</h2>
      <p>
        Hermes reads a plugin's source before it installs it, and shows you what it
        found. This plugin comes back at caution, with five findings in three
        families. Not one of them is an oversight waiting to be tidied away: each is
        part of how the plugin does its work, and each is a few lines you can read
        for yourself before you answer.
      </p>

      <.definition_list>
        <:fact term="A list of command words">
          The plugin will not hand you a command a model wrote, and to catch one it
          keeps the list of words it looks for — installers, shells, the ways of
          asking for administrator rights. A list of what to refuse has to name the
          things it refuses. One finding.
        </:fact>
        <:fact term="Three places it starts Techtree">
          Each one starts the pinned Techtree command itself: a fixed set of
          arguments, no shell, a named short list of environment variables rather
          than everything your session holds, and one answer read back. Those three
          are the whole boundary between the plugin and Techtree, and there is no
          fourth. Three findings.
        </:fact>
        <:fact term="A filter for control characters">
          It takes the control characters out of anything the plugin puts into a
          conversation, so text that arrived from somewhere else cannot redraw what
          you are reading. One finding.
        </:fact>
      </.definition_list>

      <p>
        A caution verdict is yours to answer. Hermes stops, shows you the findings,
        and installs nothing until a person confirms. Read them against the source
        they name, and confirm if you agree with what they say. The plugin's own
        README goes through the same five, in the same order.
      </p>
      <p>
        Never turn the scanning off. It is the one look at the source that happens
        before the code is on your machine, and this plugin has nothing to hide from
        it.
      </p>
    </section>
    """
  end

  @doc """
  Where the work goes and where it does not.
  """
  def disclosure(assigns) do
    ~H"""
    <p class="small quiet section">
      Techtree sends nothing on its own — publishing a finished run is a command you run,
      a run at a time, and it sends that run’s receipt and never the recordings. The
      agent under test makes real model calls, and those are sent to the model provider you
      selected, under that provider’s policies. If you later take the guided revision of your
      Skill, that one request carries your Skill text and a sanitized summary of the run to
      the provider your own agent uses.
    </p>
    """
  end

  @doc """
  For a reader who does not have Hermes yet.
  """
  def hermes_intro(assigns) do
    assigns = assign(assigns, :portal, @portal_url)

    ~H"""
    <section class="section">
      <h2>New to Hermes Agent?</h2>
      <p>
        Hermes is an open-source agent made by Nous Research. Nous Portal provides model
        access, hosted tools, and cloud-hosted Hermes under one account.
        Explore it at <a href={@portal}>{@portal}</a>.
      </p>
      <p class="small quiet">
        Techtree Hello World currently requires a Hermes host where you can install the
        plugin and CLI, access a terminal, run Docker, and authenticate with Prime. The
        Nous Portal cloud-hosted path is not yet a separately certified Techtree execution
        environment.
      </p>
    </section>
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
  defp minimum(instructions, key), do: get_in(instructions, ["minimums", key])

  defp docker_required?(instructions),
    do: get_in(instructions, ["minimums", "docker_required"]) == true

  defp introductory_slug(instructions) do
    case introductory(instructions) do
      reference when is_binary(reference) -> reference |> String.split("@") |> hd()
      _other -> nil
    end
  end

  # The words a reader hands to their agent, with one address filled in: the
  # pinned plugin release when this release names one, and the installation
  # guide on this site until it does. Both are addresses that cannot move under
  # the reader — a revision is a revision, and this page is this page.
  defp agent_prompt(instructions) do
    """
    Read the pinned Techtree installation guide at #{guide_url(instructions)}.

    If the guide says no installable release is active, stop and tell me.

    Otherwise, use only the exact plugin commit and CLI version published by the
    active release. Explain the prerequisites, the expected Hermes scanner
    findings, what may spend model tokens, and what stays local.

    Ask before:
    1. installing the Techtree plugin;
    2. installing the Techtree CLI; or
    3. starting a comparison that spends tokens.

    After the plugin is enabled, tell me when Hermes must be restarted. Then run
    Techtree Doctor, obtain the Hello World starter Skill, and prepare the
    comparison. Stop before spending until I approve it.

    Do not upload my local evaluation artifacts.
    """
    |> String.trim_trailing()
  end

  defp guide_url(instructions), do: pinned_repository_url(instructions) || @guide_url

  # The plugin release as an address, or nothing at all. A stand-in revision and
  # a branch name are both addresses that either point at nothing or point
  # somewhere different tomorrow, so neither is ever shown.
  defp pinned_repository_url(instructions) do
    repository = get_in(instructions, ["hermes_plugin", "repository"])
    revision = get_in(instructions, ["hermes_plugin", "revision"])

    if not placeholder?(instructions) and is_binary(repository) and pinned?(revision) do
      "https://github.com/" <> repository <> "/tree/" <> revision
    end
  end

  defp pinned?(revision) when is_binary(revision) do
    String.match?(revision, ~r/\A[0-9a-f]{40}\z/) and revision != @unset_revision
  end

  defp pinned?(_revision), do: false
end
