defmodule TechtreeWeb.StartLive do
  @moduledoc """
  Where a person starts, chosen by what they want to do: try the example
  Climb, evaluate their own Skill, or build tasks from their own repository.

  Each path names what it needs, roughly how long it takes and where its data
  goes. Every requirement and command is read from the active release, so the
  page cannot ask for a version the release does not publish.

  The page holds no state and no authority: every review and approval happens
  in Techtree on the person's machine.
  """

  use TechtreeWeb, :live_view

  alias TechtreeWeb.ReleaseInfo

  @title "Choose where to start."

  @impl true
  def mount(_params, _session, socket) do
    release = ReleaseInfo.current()
    minimums = if release, do: release.minimums, else: %{}

    {:ok,
     assign(socket,
       page_title: @title,
       title: @title,
       instruction: instruction(),
       minimums: minimums,
       setup_commands: setup_commands(release)
     )}
  end

  @doc """
  The instruction a person copies to their agent. It names the installation
  page rather than a version, so it stays true as releases move.
  """
  @spec instruction() :: String.t()
  def instruction do
    "Help me create a Techtree environment from one of my Skills. " <>
      "Read #{url(~p"/skill.md")} and install the exact Techtree release it names, " <>
      "or check that the one I have matches. Ask me where my Skill is. " <>
      "Then use Techtree one step at a time, show me each review exactly as Techtree prints it, " <>
      "and stop for my answer whenever it asks for a review or approval. " <>
      "Never approve anything for me."
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <section class="setup-page start-guide" aria-labelledby="start-title">
        <header class="editorial-heading">
          <p class="eyebrow">Start locally</p>
          <h1 id="start-title">{@title}</h1>
          <p class="lede">
            To see what a Skill changes, run a controlled comparison: the same agent works the same fixed tasks once without the Skill and once with it, so only the Skill changes. Techtree calls this a Climb. Try the example, bring your own Skill, or build tasks from your own repository.
          </p>
        </header>

        <Regent.Structure.panel :if={!@setup_commands} class="rg-panel__body setup-unavailable">
          <p class="eyebrow">Installation unavailable on this channel</p>
          <h2>No concrete release is available to install yet.</h2>
          <p>
            This channel does not provide installable release coordinates, so there is no instruction or command to copy yet.
          </p>
          <.link navigate={~p"/docs"} class="text-link">Read the setup documentation →</.link>
        </Regent.Structure.panel>

        <nav class="start-paths" aria-label="Ways to start">
          <a href="#example" class="start-paths__item">
            <span class="start-paths__name">Try the example</span>
            <.capability_status capability={:climb} />
            <span class="start-paths__note">Run a small, fixed Climb end to end.</span>
          </a>
          <a href="#skill" class="start-paths__item">
            <span class="start-paths__name">Evaluate my Skill</span>
            <.capability_status capability={:skill_environment} />
            <span class="start-paths__note">Turn your Skill into tasks that test it.</span>
          </a>
          <a href="#repository" class="start-paths__item">
            <span class="start-paths__name">Build tasks from my repository</span>
            <.capability_status capability={:repository_tasks} />
            <span class="start-paths__note">Turn past fixes into repair tasks.</span>
          </a>
        </nav>

        <section id="example" class="start-path" aria-labelledby="example-title">
          <header class="start-path__head">
            <.capability_status capability={:climb} />
            <h2 id="example-title">Try the example</h2>
            <p>
              The Hello World Climb is a small, fixed challenge. It runs the same tasks without a Skill and with a starter Skill that ships with the release, then shows the difference.
            </p>
          </header>
          <.definition_list>
            <:fact term="You need">
              <.requirements minimums={@minimums} provider hermes={false} />
            </:fact>
            <:fact term="Time">
              About 15 minutes to set up. The run itself depends on your model and your provider.
            </:fact>
            <:fact term="Where your data goes">
              The model calls go to your provider, only after you approve the spending limit Techtree shows you. Episodes and traces stay on your computer. Publishing a finished result is optional and uploads its proof bundle to Techtree.
            </:fact>
          </.definition_list>
          <.command_block
            :if={@setup_commands && @setup_commands.example}
            id="copy-start-example"
            label="Run the example"
            lines={@setup_commands.example}
          />
          <.link navigate={~p"/docs#first-climb"} class="text-link">
            Read the first Climb guide →
          </.link>
        </section>

        <section id="skill" class="start-path" aria-labelledby="skill-title">
          <header class="start-path__head">
            <.capability_status capability={:skill_environment} />
            <h2 id="skill-title">Evaluate my Skill</h2>
            <p>
              Give this to a coding agent that can use your terminal. It sets Techtree up, asks where your Skill is, and stops at every review for your answer.
            </p>
          </header>
          <.definition_list>
            <:fact term="You need">
              <.requirements minimums={@minimums} provider hermes />
            </:fact>
            <:fact term="Time">
              About 15 minutes to set up. Planning and building the tasks then take a while longer, depending on your Skill and your model.
            </:fact>
            <:fact term="Where your data goes">
              Nothing is uploaded to Techtree. Planning and building send your Skill's files to the model provider you chose, only after you approve the review that says so. Everything else stays on your computer until you share it.
            </:fact>
          </.definition_list>
          <.prompt_block
            :if={@setup_commands}
            id="copy-start-instruction"
            label="Give this to your agent"
            text={@instruction}
          />
          <ol class="start-steps" aria-label="What happens next">
            <li>
              <span class="eyebrow">01 / Bring a Skill</span><h3>Point to your Skill.</h3><p>
                Techtree reads its files without running any of them and tells you what it can use.
              </p>
            </li>
            <li>
              <span class="eyebrow">02 / Review</span><h3>Review the plan.</h3><p>
                Before a model sees your Skill, you see what would be sent, to which provider, and the limits. Nothing runs until you say yes.
              </p>
            </li>
            <li>
              <span class="eyebrow">03 / Create</span><h3>Keep the tasks that work.</h3><p>
                Tasks are built and checked, and you choose which to keep. Comparing with and without your Skill is optional and asks for its own approval.
              </p>
            </li>
          </ol>
          <section :if={@setup_commands} class="start-guide__direct" aria-labelledby="setup-direct">
            <h3 id="setup-direct">Or set it up yourself</h3>
            <div class="setup-page__plans">
              <.command_block id="copy-setup-cli" label="Techtree CLI" lines={@setup_commands.cli} />
              <.command_block
                id="copy-setup-hermes"
                label="Hermes plugin"
                lines={@setup_commands.hermes}
              />
            </div>
          </section>
        </section>

        <section id="repository" class="start-path" aria-labelledby="repository-title">
          <header class="start-path__head">
            <.capability_status capability={:repository_tasks} />
            <h2 id="repository-title">Build tasks from my repository</h2>
            <p>
              Point Techtree at a project with tests and a git history. It turns past fixes into repair tasks and keeps only the ones whose tests really check the fix.
            </p>
          </header>
          <.definition_list>
            <:fact term="You need">
              <.requirements minimums={@minimums} provider={false} hermes={false} />
              <p>
                A git repository with a test command. Without your own Dockerfile, it must be a Python project managed by uv.
              </p>
            </:fact>
            <:fact term="Time">
              A few minutes to set up. A build looks at ten past fixes by default and can take longer on a large project.
            </:fact>
            <:fact term="Where your data goes">
              Building makes no model calls and sends nothing to Techtree. Docker downloads a base image and your project's dependencies, and the tasks stay on your computer. Running an agent on them later sends its work to the model provider you choose.
            </:fact>
          </.definition_list>
          <.command_block
            :if={@setup_commands}
            id="copy-start-repository"
            label="Build tasks"
            lines={@setup_commands.repository}
          />
          <p class="start-path__later">
            <.capability_status capability={:hosted_building} />
            <span>A hosted service that builds these environments for you.</span>
            <.link navigate={~p"/repo2rlenv"} class="text-link">About Repo2RLEnv →</.link>
          </p>
        </section>

        <div class="start-guide__next">
          <div>
            <p class="eyebrow">Afterwards</p><h2>Keep the evidence.</h2><p>
              Techtree keeps every review, attempt and result on your computer; only the model calls you approve go to your provider.
            </p>
          </div>
          <.link navigate={~p"/verify"} class="rg-button rg-button--secondary">Understand verification →</.link>
        </div>
      </section>
    </Layouts.page>
    """
  end

  attr :minimums, :map, required: true
  attr :provider, :boolean, required: true
  attr :hermes, :boolean, required: true

  defp requirements(assigns) do
    ~H"""
    <ul class="start-path__needs">
      <li>macOS or Linux</li>
      <li :if={@minimums["uv"]}>uv {@minimums["uv"]} or later</li>
      <li :if={@minimums["python"]}>Python {@minimums["python"]}, installed for you by uv</li>
      <li :if={@minimums["docker_required"]}>Docker, running</li>
      <li :if={@hermes && @minimums["hermes_version"]}>
        Hermes {@minimums["hermes_version"]} or later
      </li>
      <li :if={@provider}>An account with a model provider; its calls may cost money</li>
    </ul>
    """
  end

  defp setup_commands(%{
         installable?: true,
         install_argv: [_ | _] = install_argv,
         plugin_install_argv: [_ | _] = plugin_install_argv,
         plugin_doctor_argv: [_ | _] = plugin_doctor_argv,
         introductory_reference: reference
       }) do
    %{
      example: example_commands(install_argv, reference),
      cli: [
        {:command, install_argv},
        {:command, ["techtree", "forge", "inspect-skill", "path/to/your-skill"]},
        {:comment, "Then plan with a provider and model you choose:"},
        {:command, ["techtree", "forge", "plan", "--help"]},
        {:comment, "Every review waits for your answer."}
      ],
      hermes: [
        {:command, plugin_install_argv},
        {:command, plugin_doctor_argv},
        {:comment, "In a fresh Hermes session, enter:"},
        {:command, ["/techtree", "setup"]}
      ],
      repository: [
        {:command, install_argv},
        {:command,
         ["techtree", "forge", "build", "--repo", "path/to/your-repo", "--test-cmd", "pytest"]},
        {:comment, "Then read what qualified:"},
        {:command, ["techtree", "forge", "status", "BUILD_ID"]}
      ]
    }
  end

  defp setup_commands(_release), do: nil

  defp example_commands(install_argv, reference) when is_binary(reference) do
    [
      {:command, install_argv},
      {:command, ["techtree", "doctor", "--climb", reference]},
      {:command, ["techtree", "skill", "starter"]},
      {:comment, "Prepare with the Skill it placed, then run the start command it prints:"},
      {:command, ["techtree", "climb", "prepare", reference, "--skill", "path/to/skill"]}
    ]
  end

  defp example_commands(_install_argv, _reference), do: nil
end
