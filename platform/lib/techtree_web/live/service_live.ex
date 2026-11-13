defmodule TechtreeWeb.ServiceLive do
  @moduledoc """
  One service's page, from its entry in `TechtreeWeb.Services`: Skills, Evals,
  Environments and Models under `/services/<service>`, each with what the
  customer brings, what we do and what they receive, the open-source tools
  used on the project, the shared terms and the service's notes, and its
  price level beside the booking action (Models adds its stages and its two
  comparisons, the parts only its entry carries); and Security at
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

  # What the page says about money beyond the price level and the terms:
  # nothing more.
  @quoted "Quoted on a call."
  @tools_line "Open-source libraries we use on your project, each named with its maker."

  @impl true
  def mount(_params, _session, socket) do
    service = Services.fetch!(socket.assigns.live_action)

    {:ok,
     assign(socket,
       page_title: service.name,
       service: service,
       mailto: mailto(service),
       quoted: @quoted,
       tools_line: @tools_line,
       terms: Services.terms()
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

    [
      "# #{service.name}\n\n#{service.promise}",
      service[:more],
      "Price level: #{service.price} of 4. #{@quoted}",
      "## You bring\n\n#{list(service.bring)}",
      "## We do\n\n#{service.work |> Enum.map(&words_markdown/1) |> list()}",
      "## You receive\n\n#{list(service.receive)}",
      stages_markdown(service[:stages]),
      comparisons_markdown(service[:comparisons]),
      "## Tools\n\n#{@tools_line}\n\n#{tools_markdown(service.tools)}",
      "## Terms\n\n#{list(Services.terms())}",
      notes_markdown(service.notes),
      "## Contact\n\n#{service.call} #{BookCall.markdown(mailto(service))}"
    ]
    |> Enum.reject(&is_nil/1)
    |> Enum.join("\n\n")
    |> Kernel.<>("\n")
  end

  defp stages_markdown(nil), do: nil

  defp stages_markdown(stages) do
    steps =
      stages
      |> Enum.with_index(1)
      |> Enum.map_join("\n", fn {stage, index} ->
        "#{index}. **#{stage.name}**: #{stage.work} #{stage.result}"
      end)

    "## Stages\n\n#{steps}"
  end

  defp comparisons_markdown(nil), do: nil

  defp comparisons_markdown(comparisons) do
    items =
      Enum.map_join(comparisons.items, "\n", fn item ->
        "- **#{item.name}**: #{item.question} #{item.answer}"
      end)

    "## Comparisons\n\n#{comparisons.line}\n\n#{items}"
  end

  defp tools_markdown(tools),
    do: Enum.map_join(tools, "\n", &"- [#{Services.label(&1)}](#{&1.href}): #{&1.job}")

  defp notes_markdown([]), do: nil

  defp notes_markdown(notes),
    do: "## Notes\n\n#{notes |> Enum.map(&words_markdown/1) |> list()}"

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
        more={@service[:more]}
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
      </section>

      <section
        :if={@service[:stages]}
        id="stages"
        class="mk-section"
        aria-labelledby="stages-title"
      >
        <header class="mk-section__head">
          <h2 id="stages-title">Stages</h2>
        </header>
        <ol id="stages-list" class="mk-sequence" phx-hook="MarketingStagger" phx-update="ignore">
          <li :for={{stage, index} <- Enum.with_index(@service.stages, 1)} data-stagger>
            <span class="mk-sequence__index">0{index}</span>
            <h3>{stage.name}</h3>
            <p>{stage.work}</p>
            <p class="mk-sequence__result">{stage.result}</p>
          </li>
        </ol>
      </section>

      <section
        :if={@service[:comparisons]}
        id="comparisons"
        class="mk-section"
        aria-labelledby="comparisons-title"
      >
        <header class="mk-section__head">
          <h2 id="comparisons-title">Comparisons</h2>
          <p>{@service.comparisons.line}</p>
        </header>
        <div class="mk-offer mk-offer--two">
          <section
            :for={item <- @service.comparisons.items}
            id={"comparison-#{String.downcase(item.name)}"}
            aria-labelledby={"comparison-#{String.downcase(item.name)}-title"}
          >
            <h3 id={"comparison-#{String.downcase(item.name)}-title"}>{item.name}</h3>
            <p class="mk-offer__question">{item.question}</p>
            <p>{item.answer}</p>
          </section>
        </div>
      </section>

      <section id="tools" class="mk-section mk-split" aria-labelledby="tools-title">
        <header class="mk-section__head">
          <h2 id="tools-title">Tools</h2>
          <p>{@tools_line}</p>
        </header>
        <dl class="mk-tools">
          <div :for={tool <- @service.tools}>
            <dt>
              <a href={tool.href} class="mk-tools__name">
                <span class="mk-tools__maker">{tool.maker}’s</span> {tool.name}
              </a>
            </dt>
            <dd>{tool.job}</dd>
          </div>
        </dl>
      </section>

      <section id="terms" class="mk-section mk-split" aria-labelledby="terms-title">
        <header class="mk-section__head">
          <h2 id="terms-title">Terms</h2>
        </header>
        <ul class="mk-status mk-status--prose">
          <li :for={term <- @terms}>{term}</li>
        </ul>
      </section>

      <section
        :if={@service.notes != []}
        id="notes"
        class="mk-section mk-split"
        aria-labelledby="notes-title"
      >
        <header class="mk-section__head">
          <h2 id="notes-title">Notes</h2>
        </header>
        <ul class="mk-status mk-status--prose">
          <li :for={note <- @service.notes}><.words words={note} /></li>
        </ul>
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
