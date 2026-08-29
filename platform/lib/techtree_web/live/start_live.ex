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
       setup_lines: setup_lines(release)
     )}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page flush>
      <section class="setup-page" aria-labelledby="setup-instruction">
        <h1 id="setup-instruction" class="setup-page__instruction">{@instruction}</h1>
        <p class="setup-page__paths">{@setup_paths}</p>
        <div :if={@setup_lines} class="setup-page__plan">
          <.command_block
            id="copy-setup-instruction"
            label="Copy the complete setup"
            lines={@setup_lines}
          />
        </div>
        <p :if={!@setup_lines} class="release-state">
          No concrete release is available to install yet.
        </p>
      </section>
    </Layouts.page>
    """
  end

  defp setup_lines(%{
         installable?: true,
         install_argv: [_ | _] = install_argv,
         plugin_install_argv: [_ | _] = plugin_install_argv,
         plugin_doctor_argv: [_ | _] = plugin_doctor_argv,
         introductory_reference: introductory_reference
       })
       when is_binary(introductory_reference) do
    [
      {:comment, @instruction},
      {:comment, "CLI"},
      {:command, install_argv},
      {:command, ["techtree", "doctor", "--climb", introductory_reference]},
      {:comment, "Hermes plugin"},
      {:command, plugin_install_argv},
      {:command, plugin_doctor_argv},
      {:comment, "In a fresh Hermes session, enter:"},
      {:command, ["/techtree", "setup"]},
      {:comment, @approval_boundary}
    ]
  end

  defp setup_lines(_release), do: nil
end
