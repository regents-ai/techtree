defmodule TechtreeWeb.ServiceLive do
  @moduledoc """
  The paid offers: Techtree Verify at `/services/verify` and Techtree Cyber
  Assist at `/services/cyber-assist`, which lead with the Agent Wallet Bench
  result, then what the buyer gets, how an engagement runs, a sample of the
  report and the way to start a conversation; and Techtree Watchdog at
  `/services/watchdog`, the monthly subscription that watches sites a team
  proves it owns, with its own shape (how it works, the rules and what you
  get). Every page starts an email whose body already asks for what we
  need (`mailto/1`); Watchdog also shows Book Call when an address for it is
  set (`TechtreeWeb.Components.BookCall`), and has the Agent Message button
  (`TechtreeWeb.Components.AgentMessage`, topic `watchdog`): its window gives an
  agent three ways to leave the team a private message, and a signed-in person a
  form for one. The window's form acts for the signed-in person, so these pages
  read the sign-in as the account menu beside them does
  (`TechtreeWeb.Live.Session`, `:load_visitor`). Each page's Markdown is
  `priv/public/services/<offer>.md`, the same facts in words, and the Verify and
  Cyber Assist sample reports are public documents (`TechtreeWeb.PublicDocuments`).

  The bench figures are counted from the published scores
  (`TechtreeWeb.WalletBenchScores.figures/0`, the grids `/wallet-bench.json`
  serves), on the page and in its Markdown (`bench_markdown/1`), so they
  follow the bench as its results come in.
  """

  use TechtreeWeb, :live_view

  import TechtreeWeb.Components.Marketing, only: [field: 1, opening: 1]

  alias TechtreeWeb.Components.{AgentMessage, BookCall}
  alias TechtreeWeb.{Outage, WalletBenchScores}

  on_mount {TechtreeWeb.Live.Session, :load_visitor}

  @offers %{
    verify: %{
      name: "Techtree Verify",
      title: "Verify",
      icon: "shield-check",
      promise: "Prove your important workflows work.",
      lede:
        "For teams that ship quickly. We check the workflows you choose, such as how an agent sets up and uses a wallet, reproduce every failure and leave you a suite you can run again.",
      other: %{
        lead: "For a security review instead, see",
        name: "Techtree Cyber Assist",
        path: "/services/cyber-assist"
      },
      deliverables: [
        {"Agreed coverage",
         "The workflows that matter to you, and the behaviour each must show."},
        {"Reproducible failures", "Every failure with the steps and evidence to see it again."},
        {"Repeatable suite", "One script that reruns every check after each release."},
        {"Clear report", "Each check, its result and its evidence, in one table."}
      ],
      steps: [
        {"Scope", "Agree the workflows", "And the behaviour each must show"},
        {"Check", "Run every check", "Each result kept with its evidence"},
        {"Report", "Report with reproductions", "The steps to see each failure again"},
        {"Fix", "Verify the fixes", "The suite runs again after your repair"}
      ],
      sample_path: "/services/verify/sample-report",
      sample_title: "12 of 14 checks passed on our own bench.",
      sample_line: "Two failures, each reproduced with its steps and a recheck.",
      sample_rows: [
        {"Page and scores file agree", "Pass", :pass},
        {"Every result link opens and agrees", "Pass", :pass},
        {"The bundled checksum file can be used", "Fail", :fail},
        {"The download is offered on every view of a result", "Fail", :fail}
      ],
      start_line:
        "Write to build@regents.sh with what you ship, the workflows that matter most, and where we can try them (a test site is best). We reply with a proposed scope.",
      subject: "Techtree Verify",
      body: ["Company:", "Product:", "Workflows that matter most:", "Place to try them:"]
    },
    cyber_assist: %{
      name: "Techtree Cyber Assist",
      title: "Cyber Assist",
      icon: "search-check",
      promise: "Find and fix the security weaknesses that matter.",
      lede:
        "For applications and agent integrations. We validate each weakness, show how to reproduce it, rank the repairs and check that each fix holds.",
      other: %{
        lead: "To check that your workflows work, see",
        name: "Techtree Verify",
        path: "/services/verify"
      },
      deliverables: [
        {"Validated findings", "Only weaknesses we reproduced, each with a priority."},
        {"Reproduction evidence", "The inputs, steps and records that show each one."},
        {"Ranked repairs", "A proposed fix for each finding, most urgent first."},
        {"Fixes verified", "Each fix checked again on the same inputs."}
      ],
      steps: [
        {"Scope", "Agree the scope", "Your application or agent integration"},
        {"Check", "Find and validate", "Only reproduced weaknesses count"},
        {"Report", "Report with reproductions", "Evidence and repairs, most urgent first"},
        {"Fix", "Verify the fixes", "Each fix rechecked on the same inputs"}
      ],
      sample_path: "/services/cyber-assist/sample-report",
      sample_title: "One validated finding on our own bench.",
      sample_line:
        "Secrets printed in colour could slip past the step that hides them in public test records. Fixed, verified and released on 28 October 2026.",
      sample_rows: [
        {"Secrets printed in colour could pass the hiding step", "Medium, fixed", :fixed},
        {"The hiding step also hid the bundled checksums", "Low, fixed", :fixed}
      ],
      start_line:
        "Write to build@regents.sh with what you build, where you want a second look, and where we can try it (a test site is best). We reply with a proposed scope.",
      subject: "Techtree Cyber Assist",
      body: ["Company:", "Product:", "Parts for a second look:", "Place to try it:"]
    },
    watchdog: %{
      name: "Techtree Watchdog",
      title: "Watchdog",
      promise: "Keep watch on the sites you own.",
      lede:
        "A monthly subscription for teams. You list the web addresses you own, prove they're yours, and we safely test them for security weaknesses the way a careful attacker would, inside limits you agree, and nothing else.",
      steps: [
        {"List", "You add the web addresses you want watched, each one a site you own."},
        {"Prove",
         "You prove each site is yours: a short DNS record, or a small file at a set address. No proof, no testing."},
        {"Watch", "We test the proven addresses for weaknesses, inside the limits you agreed."},
        {"Report",
         "You get only the weaknesses we reproduced, each with a fix, and we retest after you fix."}
      ],
      rules: [
        "Only sites you've proven you own.",
        "Only the addresses you list, nothing beyond them.",
        "A rate you agree, and never anything that deletes or changes your data.",
        "Test accounts you make for us, never a real person's login.",
        "We stop the moment you ask."
      ],
      deliverables: [
        {"Reproduced findings",
         "Only weaknesses we could show again, each with how serious it is."},
        {"Repair advice", "Clear repair advice, most urgent first."},
        {"Retest", "After you fix, we check the weakness is gone."}
      ],
      start_line:
        "Write to build@regents.sh with your company, the sites you want watched, and who we contact. We reply with a proposed scope.",
      subject: "Techtree Watchdog",
      body: ["Company:", "Sites:", "Contact:"]
    }
  }

  @impl true
  def mount(_params, _session, socket) do
    offer = Map.fetch!(@offers, socket.assigns.live_action)

    {:ok,
     assign(socket,
       page_title: offer.name,
       offer: offer,
       service: socket.assigns.live_action |> Atom.to_string() |> String.replace("_", "-"),
       bench: figures(),
       mailto: mailto(socket.assigns.live_action),
       book_call: BookCall.address()
     )}
  end

  @doc "Watchdog's Markdown line for booking a call: empty when no address is set."
  @spec book_call_markdown() :: String.t()
  def book_call_markdown do
    case BookCall.address() do
      nil -> ""
      address -> "[Book a call](#{address}), or write to us.\n\n"
    end
  end

  @doc "Watchdog's Markdown for an agent: the three ways it leaves the team a message."
  @spec agent_message_markdown() :: String.t()
  def agent_message_markdown, do: AgentMessage.markdown("watchdog")

  @doc "The email an offer starts: to build@regents.sh, with its subject and the lines its body asks for."
  @spec mailto(:verify | :cyber_assist | :watchdog) :: String.t()
  def mailto(offer) do
    %{subject: subject, body: lines} = Map.fetch!(@offers, offer)
    query = URI.encode_query([subject: subject, body: Enum.join(lines, "\r\n")], :rfc3986)
    "mailto:build@regents.sh?" <> query
  end

  @doc "The bench figures from the published scores, or `:database_down` when they can't be read."
  @spec figures() :: {:ok, WalletBenchScores.figures()} | :database_down
  def figures, do: Outage.read(&WalletBenchScores.figures/0)

  @doc "The bench paragraph of an offer's Markdown, the same words as the page's figures."
  @spec bench_markdown({:ok, WalletBenchScores.figures()} | :database_down) :: String.t()
  def bench_markdown({:ok, figures}) do
    [agents, wallets, safety] =
      for {figure, label} <- bench(figures), do: figure <> " " <> label

    "#{tested(figures)}: #{agents}; #{wallets}. #{safety}. [See the bench](/wallet-bench)."
  end

  def bench_markdown(:database_down),
    do: "The bench figures can't be shown right now. [See the bench](/wallet-bench)."

  defp bench(figures) do
    [
      {Integer.to_string(figures.agents), plural(figures.agents, "coding agent") <> " tested"},
      {"#{figures.plain_file} of #{figures.working}",
       plural(figures.working, "working wallet") <>
         " they set up left their key or unlock password in a plain file"},
      {Integer.to_string(figures.safety),
       plural(figures.safety, "safety failure") <>
         " in #{figures.judged} " <> plural(figures.judged, "judged test")}
    ]
  end

  defp signed_in(%{principal: {:human, account}}), do: account
  defp signed_in(_access_context), do: nil

  defp plural(1, noun), do: noun
  defp plural(_count, noun), do: noun <> "s"

  defp tested(%{first_day: nil}), do: "Our own bench, no tests judged yet"

  defp tested(%{first_day: first, last_day: last}),
    do: "Our own bench, tests run " <> days(first, last)

  defp days(day, day), do: date(day, "%-d %B %Y")

  defp days(%{year: year, month: month} = first, %{year: year, month: month} = last),
    do: date(first, "%-d") <> " to " <> date(last, "%-d %B %Y")

  defp days(%{year: year} = first, %{year: year} = last),
    do: date(first, "%-d %B") <> " to " <> date(last, "%-d %B %Y")

  defp days(first, last), do: date(first, "%-d %B %Y") <> " to " <> date(last, "%-d %B %Y")

  defp date(day, format), do: Calendar.strftime(day, format)

  @impl true
  def render(%{live_action: :watchdog} = assigns) do
    ~H"""
    <Layouts.page wide flush>
      <.opening
        eyebrow="Services"
        title={@offer.title}
        line={@offer.promise}
        more={@offer.lede}
        service={@service}
        icon="radar"
      >
        <:actions>
          <a class="rg-button rg-button--primary" href={@mailto}>Email us</a>
        </:actions>
        <p id="other-offers" class="mk-opening__note">
          For a one-off check instead, see <a href={~p"/services/verify"}>Techtree Verify</a>
          and <a href={~p"/services/cyber-assist"}>Techtree Cyber Assist</a>.
        </p>
      </.opening>

      <section id="steps" class="mk-section" aria-labelledby="watchdog-how-title">
        <header class="mk-section__head">
          <p class="mk-eyebrow">Process</p>
          <h2 id="watchdog-how-title">Steps</h2>
        </header>
        <ol
          id="watchdog-steps"
          class="mk-sequence"
          phx-hook="MarketingStagger"
          phx-update="ignore"
        >
          <li :for={{{title, detail}, index} <- Enum.with_index(@offer.steps, 1)} data-stagger>
            <span class="mk-sequence__index">0{index}</span>
            <h3>{title}</h3>
            <p>{detail}</p>
          </li>
        </ol>
      </section>

      <section class="mk-section mk-split" aria-labelledby="watchdog-rules-title">
        <header class="mk-section__head">
          <p class="mk-eyebrow">Limits</p>
          <h2 id="watchdog-rules-title">Rules</h2>
        </header>
        <ul id="watchdog-rules" class="mk-status">
          <li :for={rule <- @offer.rules}>{rule}</li>
        </ul>
      </section>

      <.deliverables offer={@offer} />

      <section id="contact" class="mk-band mk-dark" aria-labelledby="contact-title">
        <.field id="contact-field" scene="glow" class="mk-band__field" />
        <div class="mk-band__copy">
          <p class="mk-eyebrow">Start</p>
          <h2 id="contact-title">Contact</h2>
          <p class="mk-band__line">{@offer.start_line}</p>
          <div class="mk-band__actions">
            <BookCall.book_call />
            <a
              class={["rg-button", (@book_call && "rg-button--secondary") || "rg-button--primary"]}
              href={@mailto}
            >
              Email build@regents.sh
            </a>
            <AgentMessage.button id="watchdog-message-button" dialog="watchdog-message" />
          </div>
        </div>
      </section>
      <AgentMessage.dialog
        id="watchdog-message"
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
        title={@offer.title}
        line={@offer.promise}
        more={@offer.lede}
        service={@service}
        icon={@offer.icon}
      >
        <:actions>
          <a class="rg-button rg-button--primary" href={@mailto}>Email us</a>
        </:actions>
        <p id="other-offers" class="mk-opening__note">
          {@offer.other.lead} <a href={@offer.other.path}>{@offer.other.name}</a>.
          For ongoing watching of sites you own, see <a href={~p"/services/watchdog"}>Techtree Watchdog</a>.
        </p>
      </.opening>

      <section
        id="bench"
        class="mk-section"
        aria-labelledby="service-result-title"
        phx-hook="MarketingTally"
      >
        <header class="mk-section__head mk-section__head--row">
          <div>
            <p class="mk-eyebrow">
              {case @bench do
                {:ok, figures} -> tested(figures)
                :database_down -> "Our own bench"
              end}
            </p>
            <h2 id="service-result-title">Wallet Bench</h2>
          </div>
          <a class="text-link" href={~p"/wallet-bench"}>See the bench →</a>
        </header>
        <%= case @bench do %>
          <% {:ok, figures} -> %>
            <dl id="bench-figures" class="mk-tallies">
              <div :for={{figure, label} <- bench(figures)}>
                <dt>{label}</dt>
                <dd data-tally>{figure}</dd>
              </div>
            </dl>
          <% :database_down -> %>
            <p class="empty-state" role="status">
              The bench figures can't be shown right now. Try again in a minute.
            </p>
        <% end %>
      </section>

      <.deliverables offer={@offer} />

      <section id="steps" class="mk-section" aria-labelledby="service-how-title">
        <header class="mk-section__head">
          <p class="mk-eyebrow">Process</p>
          <h2 id="service-how-title">Steps</h2>
        </header>
        <ol id="service-steps" class="mk-sequence" phx-hook="MarketingStagger" phx-update="ignore">
          <li
            :for={{{stage, title, detail}, index} <- Enum.with_index(@offer.steps, 1)}
            data-stagger
          >
            <span class="mk-sequence__index">0{index} / {stage}</span>
            <h3>{title}</h3>
            <p>{detail}</p>
          </li>
        </ol>
      </section>

      <section class="mk-section mk-split" aria-labelledby="service-sample-title">
        <header class="mk-section__head">
          <h2 id="service-sample-title">Sample report</h2>
          <p>{@offer.sample_title} {@offer.sample_line}</p>
          <p class="mk-links">
            <a class="text-link" href={@offer.sample_path}>Read the sample report →</a>
          </p>
        </header>
        <ul class="mk-outcomes">
          <li :for={{label, result, mark} <- @offer.sample_rows}>
            <span>{label}</span>
            <strong class={["mk-outcome", "mk-outcome--#{mark}"]}>{result}</strong>
          </li>
        </ul>
      </section>

      <section id="contact" class="mk-band mk-dark" aria-labelledby="contact-title">
        <.field id="contact-field" scene="glow" class="mk-band__field" />
        <div class="mk-band__copy">
          <p class="mk-eyebrow">Start</p>
          <h2 id="contact-title">Contact</h2>
          <p class="mk-band__line">{@offer.start_line}</p>
          <div class="mk-band__actions">
            <a class="rg-button rg-button--primary" href={@mailto}>Email build@regents.sh</a>
            <BookCall.book_call variant={:secondary} />
          </div>
        </div>
      </section>
    </Layouts.page>
    """
  end

  attr :offer, :map, required: true

  defp deliverables(assigns) do
    ~H"""
    <section class="mk-section mk-split" aria-labelledby="service-get-title">
      <header class="mk-section__head">
        <p class="mk-eyebrow">Deliverables</p>
        <h2 id="service-get-title">You get</h2>
      </header>
      <dl class="mk-facts">
        <div :for={{title, detail} <- @offer.deliverables}>
          <dt>{title}</dt>
          <dd>{detail}</dd>
        </div>
      </dl>
    </section>
    """
  end
end
