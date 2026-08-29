defmodule TechtreeWeb.StartLive do
  @moduledoc """
  The one instruction for setting up Techtree and starting the introductory Climb.
  """

  use TechtreeWeb, :live_view

  @instruction "Set up Techtree and run the Hello World Climb."

  @impl true
  def mount(_params, _session, socket) do
    {:ok, assign(socket, page_title: @instruction, instruction: @instruction)}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page flush>
      <section class="setup-page" aria-labelledby="setup-instruction">
        <h1 id="setup-instruction" class="setup-page__instruction">{@instruction}</h1>
        <button
          id="copy-setup-instruction"
          class="setup-page__copy"
          type="button"
          phx-hook="CopyCommand"
          phx-update="ignore"
          data-copy-value={@instruction}
        >
          <span data-copy-label>Copy</span>
        </button>
      </section>
    </Layouts.page>
    """
  end
end
