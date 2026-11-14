defmodule TechtreeWeb.TeamMessagesLive do
  @moduledoc """
  What reaches Techtree's team, for the site's admins only, in two tabs: the
  messages agents and people left (`Techtree.Messages.Message`), and the
  enquiries visitors sent from the contact form (`Techtree.Messages.Enquiry`,
  `?show=enquiries`). Each is newest first, 50 a page. The route sits behind
  `TechtreeWeb.TeamGate`, and each read's own policy asks again
  (`RegentAgents.Checks.Admin`). `?after=` holds the cursor of the page before.
  """

  use TechtreeWeb, :live_view

  alias Regent.Primitives
  alias Techtree.Messages
  alias TechtreeWeb.{Read, Services, TeamGate}

  @impl true
  def mount(_params, _session, socket) do
    {:ok,
     assign(socket,
       page_title: "Messages",
       show: :messages,
       messages: %Read{},
       enquiries: %Read{}
     )}
  end

  @impl true
  def handle_params(params, _uri, socket) do
    case TeamGate.admin(socket.assigns.access_context) do
      nil ->
        {:noreply, redirect(socket, to: ~p"/")}

      admin ->
        show = tab(params)
        cursor = params["after"]
        page = if cursor, do: [after: cursor], else: []

        {:noreply,
         socket
         |> assign(:show, show)
         |> Read.now(show, cursor, fn -> list(show, actor: admin, page: page) end)}
    end
  end

  defp tab(%{"show" => "enquiries"}), do: :enquiries
  defp tab(_params), do: :messages

  defp list(:messages, opts), do: Messages.list_messages(opts)
  defp list(:enquiries, opts), do: Messages.list_enquiries(opts)

  # The tab's own address, with the cursor of the page before when there is one.
  defp tab_path(:messages, []), do: ~p"/admin/messages"
  defp tab_path(:enquiries, query), do: ~p"/admin/messages?#{[show: "enquiries"] ++ query}"
  defp tab_path(:messages, query), do: ~p"/admin/messages?#{query}"

  # A visitor's address as a link that writes to it and nothing more: anything
  # but its letters, digits and @ is escaped, so it cannot add a subject,
  # copies or text of its own.
  defp mailto(email), do: "mailto:" <> URI.encode(email, &(&1 == ?@ or URI.char_unreserved?(&1)))

  @impl true
  def render(assigns) do
    assigns = assign(assigns, :read, Map.fetch!(assigns, assigns.show))

    ~H"""
    <Layouts.page>
      <article class="team-messages" aria-labelledby="team-messages-title">
        <header class="editorial-heading">
          <p class="eyebrow">Team</p>
          <h1 id="team-messages-title">Messages</h1>
        </header>
        <Primitives.tabs
          id="team-tabs"
          label="Team inbox"
          tabs={[
            %{label: "Messages", patch: tab_path(:messages, []), current: @show == :messages},
            %{label: "Enquiries", patch: tab_path(:enquiries, []), current: @show == :enquiries}
          ]}
        />
        <Primitives.notice :if={@read.state in [:error, :stale]} tone="error">
          The {@show} couldn’t be read. Refresh the page to try again.
        </Primitives.notice>
        <Primitives.empty_state
          :if={@show == :messages and match?(%{state: :ready, value: %{results: []}}, @read)}
          title="No messages"
        >
          Messages agents and people leave for the team show here.
        </Primitives.empty_state>
        <Primitives.empty_state
          :if={@show == :enquiries and match?(%{state: :ready, value: %{results: []}}, @read)}
          title="No enquiries"
        >
          Enquiries visitors send from the contact form show here.
        </Primitives.empty_state>
        <ol
          :if={@show == :messages and @read.state == :ready}
          id="team-messages"
          class="team-messages__list"
        >
          <li :for={message <- @read.value.results} id={"message-#{message.id}"}>
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
                <dd><.sent at={message.inserted_at} /></dd>
              </div>
              <div :if={message.reply_to}>
                <dt>Reply</dt>
                <dd><bdi>{message.reply_to}</bdi></dd>
              </div>
            </dl>
            <p class="team-messages__body">{message.body}</p>
          </li>
        </ol>
        <ol
          :if={@show == :enquiries and @read.state == :ready}
          id="team-enquiries"
          class="team-messages__list"
        >
          <li :for={enquiry <- @read.value.results} id={"enquiry-#{enquiry.id}"}>
            <dl class="team-messages__meta">
              <div>
                <dt>Service</dt>
                <dd>{Services.fetch!(enquiry.service).name}</dd>
              </div>
              <div>
                <dt>From</dt>
                <dd><bdi>{enquiry.name}</bdi>, <bdi>{enquiry.company}</bdi></dd>
              </div>
              <div>
                <dt>Email</dt>
                <dd>
                  <a href={mailto(enquiry.email)}><bdi>{enquiry.email}</bdi></a>
                </dd>
              </div>
              <div>
                <dt>Sent</dt>
                <dd><.sent at={enquiry.inserted_at} /></dd>
              </div>
            </dl>
            <p class="team-messages__body">{enquiry.goal}</p>
          </li>
        </ol>
        <.link
          :if={@read.state == :ready and @read.value.more?}
          patch={tab_path(@show, after: List.last(@read.value.results).__metadata__.keyset)}
          class="rg-button rg-button--secondary"
        >
          Older
        </.link>
      </article>
    </Layouts.page>
    """
  end

  attr :at, DateTime, required: true

  defp sent(assigns) do
    ~H"""
    <time datetime={DateTime.to_iso8601(@at)}>
      {Calendar.strftime(@at, "%-d %b %Y, %H:%M UTC")}
    </time>
    """
  end
end
