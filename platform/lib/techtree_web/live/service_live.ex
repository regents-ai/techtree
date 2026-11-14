defmodule TechtreeWeb.ServiceLive do
  @moduledoc """
  One service's page, from its entry in `TechtreeWeb.Services`: Skills, Evals,
  Environments and Models under `/services/<service>`, each with its process
  as numbered steps (a step that runs something carries its status, Tested or
  Planned, beside its name, and one line says what the two words mean), what
  the customer receives, the open-source tools for the project grouped by
  status, the shared terms and the service's notes, and its price level
  beside the booking action (Models adds its two comparisons, the part only
  its entry carries); and Security at `/services/security`, with its two
  options (a one-off review and monthly monitoring of sites a team proves it
  owns) and the rules monitoring keeps.

  Every page ends on Contact: booking a call (`TechtreeWeb.Components.BookCall`),
  an email, and the enquiry form with the page's service already chosen
  (`TechtreeWeb.Components.Enquiry`). Security also has the Agent Message button
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

  alias TechtreeWeb.Components.{AgentMessage, BookCall, Enquiry}
  alias TechtreeWeb.Services

  on_mount {TechtreeWeb.Live.Session, :load_visitor}

  # What the page says about money beyond the price level and the terms:
  # nothing more.
  @quoted "Quoted on a call."
  @tools_line "Open-source libraries for your project, each named with its maker."

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
       status_line: Services.status_line(),
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
      "## Process\n\n#{Services.status_line()}\n\n#{steps_markdown(service.steps)}",
      "## You receive\n\n#{list(service.receive)}",
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

  defp steps_markdown(steps) do
    steps
    |> Enum.with_index(1)
    |> Enum.map_join("\n", fn {step, index} ->
      "#{index}. **#{step.name}**#{status_markdown(step.status)}: #{words_markdown(step.words)}"
    end)
  end

  defp status_markdown(nil), do: ""
  defp status_markdown(status), do: " (#{Services.status_name(status)})"

  defp comparisons_markdown(nil), do: nil

  defp comparisons_markdown(comparisons) do
    items =
      Enum.map_join(comparisons.items, "\n", fn item ->
        "- **#{item.name}**: #{item.question} #{item.answer}"
      end)

    "## Comparisons\n\n#{comparisons.line}\n\n#{items}"
  end

  defp tools_markdown(tools) do
    tools
    |> Services.by_status()
    |> Enum.map_join("\n\n", fn {status, group} ->
      "### #{Services.status_name(status)}\n\n" <>
        Enum.map_join(group, "\n", &"- [#{Services.label(&1)}](#{&1.href}): #{&1.job}")
    end)
  end

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
          class="mk-offer"
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

      <.contact service={@service} mailto={@mailto} client_key={@client_key}>
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

      <section id="process" class="mk-section" aria-labelledby="process-title">
        <header class="mk-section__head">
          <h2 id="process-title">Process</h2>
          <p>{@status_line}</p>
        </header>
        <ol id="steps" class="mk-steps" phx-hook="MarketingStagger" phx-update="ignore">
          <li
            :for={{step, index} <- Enum.with_index(@service.steps, 1)}
            id={"step-#{index}"}
            data-stagger
          >
            <span class="mk-steps__index" aria-hidden="true">
              {String.pad_leading(Integer.to_string(index), 2, "0")}
            </span>
            <div class="mk-steps__head">
              <h3>{step.name}</h3>
              <.status_word :if={step.status} status={step.status} />
            </div>
            <p class="mk-steps__words"><.words words={step.words} /></p>
          </li>
        </ol>
      </section>

      <section id="receive" class="mk-section mk-split" aria-labelledby="receive-title">
        <header class="mk-section__head">
          <h2 id="receive-title">You receive</h2>
        </header>
        <ul class="mk-status mk-status--prose">
          <li :for={item <- @service.receive}>{item}</li>
        </ul>
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
        <div class="mk-offer">
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
        <div class="mk-tools__groups">
          <section
            :for={{status, tools} <- Services.by_status(@service.tools)}
            id={"tools-#{status}"}
            aria-labelledby={"tools-#{status}-title"}
          >
            <h3 id={"tools-#{status}-title"} class="mk-tools__status">
              <.status_word status={status} />
            </h3>
            <dl class="mk-tools">
              <div :for={tool <- tools}>
                <dt>
                  <a href={tool.href} class="mk-tools__name">
                    <span class="mk-tools__maker">{tool.maker}’s</span> {tool.name}
                  </a>
                </dt>
                <dd>{tool.job}</dd>
              </div>
            </dl>
          </section>
        </div>
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

      <.contact service={@service} mailto={@mailto} client_key={@client_key} />
    </Layouts.page>
    """
  end

  attr :words, :list, required: true

  # A sentence's words and links, run together with no space of their own, so
  # a link sits right against the comma or full stop after it.
  defp words(assigns) do
    ~H"""
    <.word :for={part <- @words} part={part} />
    """
  end

  attr :part, :any, required: true

  defp word(%{part: {text, href}} = assigns) do
    assigns = assign(assigns, text: text, href: href)
    ~H|<a href={@href}>{@text}</a>|
  end

  defp word(assigns), do: ~H|{@part}|

  attr :status, :atom, required: true

  # A status in its one word, quiet beside what it marks: only Delivered takes
  # a colour.
  defp status_word(assigns) do
    ~H"""
    <Regent.Primitives.status
      tone={if(@status == :delivered, do: "success", else: "neutral")}
      class="mk-status-word"
      data-status={@status}
    >
      {Services.status_name(@status)}
    </Regent.Primitives.status>
    """
  end

  attr :service, :map, required: true
  attr :mailto, :string, required: true
  attr :client_key, :string, required: true
  slot :inner_block

  # The call, the email and the enquiry form side by side, the form under them
  # on a narrow screen.
  defp contact(assigns) do
    ~H"""
    <section id="contact" class="mk-band mk-dark mk-contact" aria-labelledby="contact-title">
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
      <.live_component module={Enquiry} id="enquiry" service={@service.id} client_key={@client_key} />
    </section>
    """
  end
end
