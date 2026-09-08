defmodule TechtreeWeb.StartLive do
  @moduledoc """
  The one instruction for setting up Techtree and starting the introductory Climb.
  """

  use TechtreeWeb, :live_view

  alias TechtreeWeb.ReleaseInfo

  @instruction "Set up Techtree and run the Hello World Climb."
  @setup_paths "Choose the Techtree CLI or Hermes plugin path below."
  @approval_boundary "Follow Doctor's exact next action. Ask before starting paid model inference."

  @impl true
  def mount(_params, _session, socket) do
    release = ReleaseInfo.current()

    {:ok,
     assign(socket,
       page_title: @instruction,
       instruction: @instruction,
       setup_paths: @setup_paths,
       setup_commands: setup_commands(release)
     )}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <section class="setup-page start-guide" aria-labelledby="setup-instruction">
        <header class="editorial-heading">
          <p class="eyebrow">Start locally</p>
          <h1 id="setup-instruction">Your first controlled run.</h1>
          <p class="lede">{@instruction} {@setup_paths}</p>
        </header>
        <ol class="start-steps" aria-label="Setup sequence">
          <li>
            <span class="eyebrow">01 / Install</span><h2>Choose your interface.</h2><p>
              Use the CLI directly or work inside Hermes. Both use the same Techtree runtime.
            </p>
          </li>
          <li>
            <span class="eyebrow">02 / Check</span><h2>Let Doctor guide you.</h2><p>
              Check the machine and the Climb before running. Follow the exact next action it returns.
            </p>
          </li>
          <li>
            <span class="eyebrow">03 / Run</span><h2>Approve, then compare.</h2><p>
              Confirm any paid inference first. Inspect the local Result before choosing whether to publish.
            </p>
          </li>
        </ol>
        <div :if={@setup_commands} class="setup-page__plans">
          <.command_block
            id="copy-setup-cli"
            label="CLI setup"
            lines={@setup_commands.cli}
          />
          <.command_block
            id="copy-setup-hermes"
            label="Hermes plugin setup"
            lines={@setup_commands.hermes}
          />
        </div>
        <Regent.Structure.panel :if={!@setup_commands} class="rg-panel__body setup-unavailable">
          <p class="eyebrow">Installation unavailable on this channel</p>
          <h2>No concrete release is available to install yet.</h2>
          <p>
            This channel does not provide installable release coordinates. No placeholder command will be offered.
          </p>
          <.link navigate={~p"/docs"} class="text-link">Read the setup documentation →</.link>
        </Regent.Structure.panel>
        <div class="start-guide__next">
          <div>
            <p class="eyebrow">After the run</p><h2>Keep the evidence.</h2><p>
              A Result can show uplift, a tie, or regression. Verification checks the bundle—not whether someone else reproduced the run.
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
         plugin_doctor_argv: [_ | _] = plugin_doctor_argv,
         introductory_reference: introductory_reference
       })
       when is_binary(introductory_reference) do
    %{
      cli: [
        {:comment, @instruction},
        {:command, install_argv},
        {:command, ["techtree", "doctor", "--climb", introductory_reference]},
        {:comment, @approval_boundary}
      ],
      hermes: [
        {:comment, @instruction},
        {:command, plugin_install_argv},
        {:command, plugin_doctor_argv},
        {:comment, "In a fresh Hermes session, enter:"},
        {:command, ["/techtree", "setup"]},
        {:comment, @approval_boundary}
      ]
    }
  end

  defp setup_commands(_release), do: nil
end
