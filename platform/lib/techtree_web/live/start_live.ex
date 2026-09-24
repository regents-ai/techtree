defmodule TechtreeWeb.StartLive do
  @moduledoc """
  One instruction a person gives their own local agent to create an
  environment from a Skill, with the direct setup commands as secondary detail.

  The page holds no state and no authority: the agent reads the release's own
  installation page, and every review and approval happens in Techtree on the
  person's machine.
  """

  use TechtreeWeb, :live_view

  alias TechtreeWeb.ReleaseInfo

  @title "Create an environment from your Skill."

  @impl true
  def mount(_params, _session, socket) do
    release = ReleaseInfo.current()

    {:ok,
     assign(socket,
       page_title: @title,
       title: @title,
       instruction: instruction(),
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
      <section class="setup-page start-guide" aria-labelledby="setup-instruction">
        <header class="editorial-heading">
          <p class="eyebrow">Start locally</p>
          <h1 id="setup-instruction">{@title}</h1>
          <p class="lede">
            Give this to a coding agent that can use your terminal. It sets Techtree up, asks where your Skill is, and stops at every review for your answer.
          </p>
        </header>
        <.prompt_block
          :if={@setup_commands}
          id="copy-start-instruction"
          label="Give this to your agent"
          text={@instruction}
        />
        <Regent.Structure.panel :if={!@setup_commands} class="rg-panel__body setup-unavailable">
          <p class="eyebrow">Installation unavailable on this channel</p>
          <h2>No concrete release is available to install yet.</h2>
          <p>
            This channel does not provide installable release coordinates, so there is no instruction or command to copy yet.
          </p>
          <.link navigate={~p"/docs"} class="text-link">Read the setup documentation →</.link>
        </Regent.Structure.panel>
        <ol class="start-steps" aria-label="What happens next">
          <li>
            <span class="eyebrow">01 / Bring a Skill</span><h2>Point to your Skill.</h2><p>
              Techtree reads its files without running any of them and tells you what it can use.
            </p>
          </li>
          <li>
            <span class="eyebrow">02 / Review</span><h2>Review the plan.</h2><p>
              Before a model sees your Skill, you see what would be sent, to which provider, and the limits. Nothing runs until you say yes.
            </p>
          </li>
          <li>
            <span class="eyebrow">03 / Create</span><h2>Keep the tasks that work.</h2><p>
              Tasks are built and checked, and you choose which to keep. The result stays on your computer until you share it.
            </p>
          </li>
        </ol>
        <section :if={@setup_commands} class="start-guide__direct" aria-labelledby="setup-direct">
          <h2 id="setup-direct">Or set it up yourself</h2>
          <div class="setup-page__plans">
            <.command_block id="copy-setup-cli" label="Techtree CLI" lines={@setup_commands.cli} />
            <.command_block
              id="copy-setup-hermes"
              label="Hermes plugin"
              lines={@setup_commands.hermes}
            />
          </div>
        </section>
        <div class="start-guide__next">
          <div>
            <p class="eyebrow">Afterwards</p><h2>Keep the evidence.</h2><p>
              Techtree keeps every review, attempt and result on your computer; only the model calls you approve go to your provider. Running the tasks, or comparing with and without your Skill, is optional and asks for its own approval.
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
         plugin_install_argv: [_ | _] = plugin_install_argv,
         plugin_doctor_argv: [_ | _] = plugin_doctor_argv
       }) do
    %{
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
      ]
    }
  end

  defp setup_commands(_release), do: nil
end
