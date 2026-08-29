defmodule TechtreeWeb.StartLive do
  @moduledoc """
  The one instruction for setting up Techtree and starting the introductory Climb.
  """

  use TechtreeWeb, :live_view

  @instruction "Set up Techtree and run the Hello World Climb."
  @setup_paths "Use the Techtree CLI or Hermes plugin."
  @copy_instruction "#{@instruction} #{@setup_paths}"

  @impl true
  def mount(_params, _session, socket) do
    {:ok,
     assign(socket,
       page_title: @instruction,
       instruction: @instruction,
       setup_paths: @setup_paths,
       copy_instruction: @copy_instruction
     )}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page flush>
      <section class="setup-page" aria-labelledby="setup-instruction">
        <h1 id="setup-instruction" class="setup-page__instruction">{@instruction}</h1>
        <p class="setup-page__paths">{@setup_paths}</p>
        <button
          id="copy-setup-instruction"
          class="setup-page__copy"
          type="button"
          phx-hook="CopyCommand"
          phx-update="ignore"
          data-copy-value={@copy_instruction}
        >
          <span data-copy-label>Copy</span>
        </button>
      </section>
    </Layouts.page>
    """
  end
end
