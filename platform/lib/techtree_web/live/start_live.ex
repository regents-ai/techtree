defmodule TechtreeWeb.StartLive do
  @moduledoc """
  Where a person starts, chosen by what they want to do: test their own
  Skill, or take a quick look with the example Climb.

  Each path names what it needs, roughly how long it takes and where its data
  goes. The version requirements and the install line come from the active
  release, and the example's model, key, tasks and limits from the Campaign of
  the Climb that release introduces; the steps after the install line are
  written for the release being installed.

  The page holds no state and no authority: every review and approval happens
  in Techtree on the person's machine.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query
  alias TechtreeWeb.CampaignFacts
  alias TechtreeWeb.Providers
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
       example: example(release),
       setup_commands: setup_commands(release)
     )}
  end

  @doc """
  The instruction a person copies to their agent. It names the installation
  page rather than a version, so it stays true as releases move.
  """
  @spec instruction() :: String.t()
  def instruction do
    "Help me test one of my Skills with Techtree. " <>
      "Read #{url(~p"/skill.md")} and install the exact Techtree release it names, " <>
      "or check that the one I have matches. Ask me where my Skill is, and whether to " <>
      "compare it with no Skill or with an earlier version of it. " <>
      "Then use Techtree one step at a time to make the tasks, run them both ways and compare. " <>
      "Show me each review exactly as Techtree prints it, " <>
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
            To see what a Skill changes, Techtree makes tasks from it and your agent works them twice: once without the Skill, or with its earlier version, and once with it. Only the Skill changes, so the difference is the Skill’s. Test your own Skill, or take a quick look with the example.
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
          <a href="#skill" class="start-paths__item">
            <span class="start-paths__name">Test my Skill</span>
            <.capability_status capability={:skill_test} />
            <span class="start-paths__note">Make tasks from it, compare, decide.</span>
          </a>
          <a href="#example" class="start-paths__item">
            <span class="start-paths__name">Take a quick look</span>
            <.capability_status capability={:climb} />
            <span class="start-paths__note">Run the small Hello World example end to end.</span>
          </a>
        </nav>

        <section id="skill" class="start-path" aria-labelledby="skill-title">
          <header class="start-path__head">
            <.capability_status capability={:skill_test} />
            <h2 id="skill-title">Test my Skill</h2>
            <p>
              Give this to a coding agent that can use your terminal, or to Hermes. It sets Techtree up, asks where your Skill is, and stops at every review for your answer.
            </p>
          </header>
          <.definition_list>
            <:fact term="You need">
              <.requirements minimums={@minimums} provider hermes />
            </:fact>
            <:fact term="Time">
              About 15 minutes to set up. Making the tasks and running the comparison then take longer, depending on your Skill and your model.
            </:fact>
            <:fact term="Where your data goes">
              Nothing is uploaded to Techtree. Making the tasks and running them send your Skill's files and the tasks to the model provider you chose, only after you approve the review that says so. Everything else stays on your computer until you share it.
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
                Tasks are built and checked, and you choose which to keep. Some are held out from anyone improving the Skill.
              </p>
            </li>
            <li>
              <span class="eyebrow">04 / Compare</span><h3>Run the tasks both ways.</h3><p>
                Your agent works the tasks without the Skill, or with its earlier version, and then with it. Each run shows the most it may spend and waits for your yes.
              </p>
            </li>
            <li>
              <span class="eyebrow">05 / Decide</span><h3>Keep the change, or don’t.</h3><p>
                Techtree compares the two runs task by task and says whether the Skill improved, regressed, was mixed or made no difference, with the held-out tasks judged on their own.
              </p>
            </li>
          </ol>
          <section :if={@setup_commands} class="start-guide__direct" aria-labelledby="setup-direct">
            <h3 id="setup-direct">Or set it up yourself</h3>
            <.command_block id="copy-setup-cli" label="Command line" lines={@setup_commands.cli} />
            <.link navigate={~p"/docs#test-skill"} class="text-link">
              Every step, including the comparison →
            </.link>
          </section>
        </section>

        <section id="example" class="start-path" aria-labelledby="example-title">
          <header class="start-path__head">
            <.capability_status capability={:climb} />
            <h2 id="example-title">Take a quick look</h2>
            <p>
              The Hello World Climb is a small, fixed challenge that ships with the release. It runs the same tasks without a Skill and with a starter Skill, then shows the difference. It shows how a run works; its toy tasks say nothing about your own Skill.
            </p>
          </header>
          <.definition_list :if={@example}>
            <:fact term="You need">
              <.requirements minimums={@minimums} provider={false} hermes={false}>
                <li>
                  An API key for {@example.provider}, set as <code>{@example.credential_env}</code>; the model calls are charged to your account
                </li>
              </.requirements>
            </:fact>
            <:fact term="Model">
              The Climb fixes the model: <code>{@example.model_id}</code> from {@example.provider}.
            </:fact>
            <:fact term="Limits">
              Each task is tried once with the Skill and once without. Each try stops starting model calls after {@example.calls} calls, {@example.input_tokens} input tokens or {@example.output_tokens} output tokens. With {@example.tasks} tasks, a run can make up to {@example.run_calls} model calls. Before anything runs, Techtree shows the most the run may spend and waits for your yes.
            </:fact>
            <:fact term="Time">
              About 15 minutes to set up. How long the run takes depends on your provider.
            </:fact>
            <:fact term="Where your data goes">
              The model calls go to {@example.provider} on your <code>{@example.credential_env}</code>
              key, only after you approve. Episodes and traces stay on your computer. Publishing a finished result is optional and uploads its proof bundle to Techtree.
            </:fact>
          </.definition_list>
          <.command_block
            :if={@setup_commands}
            id="copy-start-example"
            label="Run the example"
            lines={@setup_commands.example}
          />
          <.link navigate={~p"/docs#first-climb"} class="text-link">
            Read the first Climb guide →
          </.link>
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

  defp setup_commands(%{
         installable?: true,
         install_argv: [_ | _] = install_argv,
         introductory_reference: reference
       }) do
    %{
      example: example_commands(install_argv, reference),
      cli: [
        {:command, install_argv},
        {:command, ["regents", "techtree", "forge", "inspect-skill", "path/to/your-skill"]},
        {:comment, "Then plan with a provider and model you choose:"},
        {:command, ["regents", "techtree", "forge", "plan", "--help"]},
        {:comment, "Every review waits for your answer."}
      ]
    }
  end

  defp setup_commands(_release), do: nil

  # What the Climb this release introduces asks of the person running it, read
  # from its Campaign. A release always names a Climb its catalog ships, and the
  # import refuses a Campaign that leaves any of these out.
  defp example(%{introductory_reference: reference}) do
    trial = reference |> Query.get_climb_by_reference!() |> CampaignFacts.trial!()

    %{
      provider: Providers.name!(trial.provider),
      model_id: trial.model_id,
      credential_env: trial.credential_env,
      tasks: CampaignFacts.count(trial.tasks),
      calls: CampaignFacts.count(trial.calls),
      input_tokens: CampaignFacts.count(trial.input_tokens),
      output_tokens: CampaignFacts.count(trial.output_tokens),
      run_calls: trial |> CampaignFacts.run_total() |> Map.fetch!(:calls) |> CampaignFacts.count()
    }
  end

  defp example(nil), do: nil

  defp example_commands(install_argv, reference) do
    [
      {:command, install_argv},
      {:command, ["regents", "techtree", "setup"]},
      {:command, ["regents", "techtree", "doctor", "--climb", reference]},
      {:command, ["regents", "techtree", "skill", "starter"]},
      {:comment, "Prepare with the Skill it placed, then run the start command it prints:"},
      {:command,
       ["regents", "techtree", "climb", "prepare", reference, "--skill", "path/to/skill"]}
    ]
  end
end
