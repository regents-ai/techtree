defmodule TechtreeWeb.ServiceLive do
  @moduledoc """
  One service's page, from its entry in `TechtreeWeb.Services`: Skills, Evals,
  Environments and Models under `/services/<service>`, each with what the
  customer brings, what we do and what they receive, and its price level
  beside the booking action; and Security at
  `/services/security`, with its two options (a one-off review and monthly
  monitoring of sites a team proves it owns) and the rules monitoring keeps.

  Every page ends on booking a call (`TechtreeWeb.Components.BookCall`) or
  writing to us. Security also has the Agent Message button
  (`TechtreeWeb.Components.AgentMessage`, topic `watchdog`): its window gives
  an agent three ways to leave the team a private message, and a signed-in
  person a form for one. The window's form acts for the signed-in person, so
  these pages read the sign-in as the account menu beside them does
  (`TechtreeWeb.Live.Session`, `:load_visitor`).

  Each page's Markdown (`markdown/1`) is built from the same entry, so the two
  never say different things.
  """

  use TechtreeWeb, :live_view

  import TechtreeWeb.Components.Marketing, only: [field: 1, opening: 1, price: 1]

  alias TechtreeWeb.Components.{AgentMessage, BookCall}
  alias TechtreeWeb.Services

  on_mount {TechtreeWeb.Live.Session, :load_visitor}

  # What the page says about money beyond the price level: nothing more.
  @quoted "Quoted on a call."

  @impl true
  def mount(_params, _session, socket) do
    service = Services.fetch!(socket.assigns.live_action)

    {:ok,
     assign(socket,
       page_title: service.name,
       service: service,
       mailto: mailto(service),
       quoted: @quoted
     )}
  end

  @doc "A service's page as Markdown: the same words, with the call and the email."
  @spec markdown(atom()) :: String.t()
  def markdown(:security) do
    service = Services.security()

    options =
      Enum.map_join(service.options, "\n\n", fn option ->
        {label, href} = option.link

        "## #{option.name}\n\n#{option.line}\n\n#{list(option.items)}\n\n[#{label}](#{href})"
      end)

    """
    # #{service.name}

    #{service.promise}

    #{options}

    ## Rules

    #{list(service.rules)}

    ## Contact

    #{service.call} #{BookCall.markdown(mailto(service))}

    #{AgentMessage.markdown("watchdog")}
    """
  end

  def markdown(id) do
    service = Services.fetch!(id)
    note = if service.note, do: "\n\n" <> service.note, else: ""

    """
    # #{service.name}

    #{service.promise}

    Price level: #{service.price} of 4. #{@quoted}

    ## You bring

    #{list(service.bring)}

    ## We do

    #{service.work |> Enum.map(&words_markdown/1) |> list()}

    ## You receive

    #{list(service.receive)}#{note}

    ## Contact

    #{service.call} #{BookCall.markdown(mailto(service))}
    """
  end

  defp list(items), do: Enum.map_join(items, "\n", &("- " <> &1))

  defp words_markdown(words) do
    Enum.map_join(words, fn
      {text, href} -> "[#{text}](#{href})"
      text -> text
    end)
  end

  defp mailto(service),
    do: "mailto:build@regents.sh?" <> URI.encode_query([subject: service.name], :rfc3986)

  defp signed_in(%{principal: {:human, account}}), do: account
  defp signed_in(_access_context), do: nil

  @impl true
  def render(%{live_action: :security} = assigns) do
    ~H"""
    <Layouts.page wide flush>
      <.opening
        eyebrow="Services"
        title={@service.name}
        line={@service.promise}
        service="security"
        icon={@service.icon}
        book_call={false}
      >
        <:actions>
          <BookCall.book_call />
          <a class="rg-button rg-button--secondary" href={@mailto}>Email us</a>
        </:actions>
      </.opening>

      <section id="options" class="mk-section" aria-labelledby="options-title">
        <header class="mk-section__head">
          <h2 id="options-title">Options</h2>
        </header>
        <div
          id="options-list"
          class="mk-offer mk-offer--two"
          phx-hook="MarketingStagger"
          phx-update="ignore"
        >
          <section
            :for={option <- @service.options}
            id={option.id}
            aria-labelledby={"#{option.id}-title"}
            data-stagger
          >
            <h3 id={"#{option.id}-title"}>{option.name}</h3>
            <p>{option.line}</p>
            <ul>
              <li :for={item <- option.items}>{item}</li>
            </ul>
            <a class="text-link" href={elem(option.link, 1)}>
              {elem(option.link, 0)} <span aria-hidden="true">→</span>
            </a>
          </section>
        </div>
      </section>

      <section class="mk-section mk-split" aria-labelledby="rules-title">
        <header class="mk-section__head">
          <p class="mk-eyebrow">Monitoring</p>
          <h2 id="rules-title">Rules</h2>
        </header>
        <ul id="rules" class="mk-status">
          <li :for={rule <- @service.rules}>{rule}</li>
        </ul>
      </section>

      <.contact service={@service} mailto={@mailto}>
        <AgentMessage.button id="security-message-button" dialog="security-message" />
      </.contact>
      <AgentMessage.dialog
        id="security-message"
        topic="watchdog"
        account={signed_in(@access_context)}
        lease={@session_lease}
        client_key={@client_key}
      />
    </Layouts.page>
    """
  end

  def render(assigns) do
    ~H"""
    <Layouts.page wide flush>
      <.opening
        eyebrow="Services"
        title={@service.name}
        line={@service.promise}
        service={Atom.to_string(@service.id)}
        icon={@service.icon}
        book_call={false}
      >
        <:actions>
          <BookCall.book_call />
          <a class="rg-button rg-button--secondary" href={@mailto}>Email us</a>
        </:actions>
        <div class="mk-opening__price" data-entrance-part>
          <.price id="price" level={@service.price} />
          <p>{@quoted}</p>
        </div>
      </.opening>

      <section id="work" class="mk-section" aria-label="The work">
        <div id="work-list" class="mk-offer" phx-hook="MarketingStagger" phx-update="ignore">
          <section id="bring" aria-labelledby="bring-title" data-stagger>
            <span class="mk-sequence__index">01</span>
            <h2 id="bring-title">You bring</h2>
            <ul>
              <li :for={item <- @service.bring}>{item}</li>
            </ul>
          </section>
          <section id="do" aria-labelledby="do-title" data-stagger>
            <span class="mk-sequence__index">02</span>
            <h2 id="do-title">We do</h2>
            <ul>
              <li :for={words <- @service.work}><.words words={words} /></li>
            </ul>
          </section>
          <section id="receive" aria-labelledby="receive-title" data-stagger>
            <span class="mk-sequence__index">03</span>
            <h2 id="receive-title">You receive</h2>
            <ul>
              <li :for={item <- @service.receive}>{item}</li>
            </ul>
          </section>
        </div>
        <p :if={@service.note} id="note" class="mk-section__note">{@service.note}</p>
      </section>

      <.contact service={@service} mailto={@mailto} />
    </Layouts.page>
    """
  end

  attr :words, :list, required: true

  defp words(assigns) do
    ~H"""
    <%= for part <- @words do %>
      <%= case part do %>
        <% {text, href} -> %>
          <a href={href}>{text}</a>
        <% text -> %>
          {text}
      <% end %>
    <% end %>
    """
  end

  attr :service, :map, required: true
  attr :mailto, :string, required: true
  slot :inner_block

  defp contact(assigns) do
    ~H"""
    <section id="contact" class="mk-band mk-dark" aria-labelledby="contact-title">
      <.field id="contact-field" scene="glow" class="mk-band__field" />
      <div class="mk-band__copy">
        <p class="mk-eyebrow">Start</p>
        <h2 id="contact-title">Contact</h2>
        <p class="mk-band__line">{@service.call}</p>
        <div class="mk-band__actions">
          <BookCall.book_call />
          <a class="rg-button rg-button--secondary" href={@mailto}>Email build@regents.sh</a>
          {render_slot(@inner_block)}
        </div>
      </div>
    </section>
    """
  end
end
