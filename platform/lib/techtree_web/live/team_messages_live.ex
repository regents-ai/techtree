defmodule TechtreeWeb.TeamMessagesLive do
  @moduledoc """
  The messages agents and people left for Techtree's team (`Techtree.Messages`),
  newest first, 50 a page, for the site's admins only: the route sits behind
  `TechtreeWeb.TeamGate`, and the read's own policy asks again
  (`RegentAgents.Checks.Admin`). `?after=` holds the cursor of the page before.
  """

  use TechtreeWeb, :live_view

  alias Regent.Primitives
  alias Techtree.Messages
  alias TechtreeWeb.{Read, TeamGate}

  @impl true
  def mount(_params, _session, socket) do
    {:ok, assign(socket, page_title: "Messages", messages: %Read{})}
  end

  @impl true
  def handle_params(params, _uri, socket) do
    case TeamGate.admin(socket.assigns.access_context) do
      nil ->
        {:noreply, redirect(socket, to: ~p"/")}

      admin ->
        cursor = params["after"]
        page = if cursor, do: [after: cursor], else: []

        {:noreply,
         Read.now(socket, :messages, cursor, fn ->
           Messages.list_messages(actor: admin, page: page)
         end)}
    end
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page>
      <article class="team-messages" aria-labelledby="team-messages-title">
        <header class="editorial-heading">
          <p class="eyebrow">Team</p>
          <h1 id="team-messages-title">Messages</h1>
        </header>
        <Primitives.notice :if={@messages.state in [:error, :stale]} tone="error">
          The messages couldn’t be read. Refresh the page to try again.
        </Primitives.notice>
        <Primitives.empty_state
          :if={match?(%{state: :ready, value: %{results: []}}, @messages)}
          title="No messages"
        >
          Messages agents and people leave for the team show here.
        </Primitives.empty_state>
        <ol :if={@messages.state == :ready} id="team-messages" class="team-messages__list">
          <li :for={message <- @messages.value.results} id={"message-#{message.id}"}>
            <dl class="team-messages__meta">
              <div>
                <dt>Topic</dt>
                <dd><code>{message.topic}</code></dd>
              </div>
              <div>
                <dt>From</dt>
                <dd>
                  <bdi>{message.sender_name}</bdi>
                  <span :if={message.agent}>
                    · Agent
                    <Primitives.address
                      id={"message-#{message.id}-agent"}
                      address={message.agent.wallet_address}
                    />
                  </span>
                </dd>
              </div>
              <div>
                <dt>Sent</dt>
                <dd>
                  <time datetime={DateTime.to_iso8601(message.inserted_at)}>
                    {Calendar.strftime(message.inserted_at, "%-d %b %Y, %H:%M UTC")}
                  </time>
                </dd>
              </div>
              <div :if={message.reply_to}>
                <dt>Reply</dt>
                <dd><bdi>{message.reply_to}</bdi></dd>
              </div>
            </dl>
            <p class="team-messages__body">{message.body}</p>
          </li>
        </ol>
        <.link
          :if={@messages.state == :ready and @messages.value.more?}
          patch={"?after=" <> List.last(@messages.value.results).__metadata__.keyset}
          class="rg-button rg-button--secondary"
        >
          Older
        </.link>
      </article>
    </Layouts.page>
    """
  end
end
