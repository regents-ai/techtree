defmodule TechtreeWeb.ServiceLive do
  @moduledoc """
  The paid offers: Techtree Verify at `/services/verify` and Techtree Cyber
  Assist at `/services/cyber-assist`, which lead with the Agent Wallet Bench
  result, then what the buyer gets, how an engagement runs, a sample of the
  report and the way to start a conversation; and Techtree Watchdog at
  `/services/watchdog`, the monthly subscription that watches sites a team
  proves it owns, with its own shape (how it works, the rules, what you get and
  the price). Every page starts an email whose body already asks for what we
  need (`mailto/1`). Each page's Markdown is `priv/public/services/<offer>.md`,
  the same facts in words, and the Verify and Cyber Assist sample reports are
  public documents (`TechtreeWeb.PublicDocuments`).

  The bench figures are counted from the published scores
  (`TechtreeWeb.WalletBenchScores.figures/0`, the grids `/wallet-bench.json`
  serves), on the page and in its Markdown (`bench_markdown/1`), so they
  follow the bench as its results come in.
  """

  use TechtreeWeb, :live_view

  alias TechtreeWeb.{Outage, WalletBenchScores}

  @offers %{
    verify: %{
      name: "Techtree Verify",
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
        {"A repeatable suite", "One script that reruns every check after each release."},
        {"A clear report", "Each check, its result and its evidence, in one table."}
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
        "Write to build@regents.sh with what you ship, the workflows that matter most, and where we can try them (a test site is best). We reply with a proposed scope; the price is set once the scope is agreed.",
      subject: "Techtree Verify",
      body: ["Company:", "Product:", "Workflows that matter most:", "Place to try them:"]
    },
    cyber_assist: %{
      name: "Techtree Cyber Assist",
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
        {"Repairs in priority order", "A proposed fix for each finding, most urgent first."},
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
        "Write to build@regents.sh with what you build, where you want a second look, and where we can try it (a test site is best). We reply with a proposed scope; the price is set once the scope is agreed.",
      subject: "Techtree Cyber Assist",
      body: ["Company:", "Product:", "Parts for a second look:", "Place to try it:"]
    },
    watchdog: %{
      name: "Techtree Watchdog",
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
        {"A fix for each", "Clear repair advice, most urgent first."},
        {"A retest", "After you fix, we check the weakness is gone."}
      ],
      price: "Monthly, per site. Ask us for the price.",
      start_line:
        "Write to build@regents.sh with your company, the sites you want watched, and who we contact. We reply with a proposed scope; the price is set once the scope is agreed.",
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
       bench: figures(),
       mailto: mailto(socket.assigns.live_action)
     )}
  end

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
    <Layouts.page wide>
      <article class="service-offer" aria-labelledby="service-title">
        <header class="editorial-heading">
          <p class="eyebrow">{@offer.name}</p>
          <h1 id="service-title">{@offer.promise}</h1>
          <p class="lede">{@offer.lede}</p>
          <div class="service-offer__actions">
            <a class="rg-button rg-button--primary" href={@mailto}>Email us</a>
          </div>
          <p class="service-offer__other">
            For a one-off check instead, see <a href={~p"/services/verify"}>Techtree Verify</a>
            and <a href={~p"/services/cyber-assist"}>Techtree Cyber Assist</a>.
          </p>
        </header>

        <section class="service-offer__flow" aria-labelledby="watchdog-how-title">
          <p class="eyebrow">Process</p>
          <h2 id="watchdog-how-title">How it works</h2>
          <ol class="service-flow">
            <li :for={{{title, detail}, index} <- Enum.with_index(@offer.steps, 1)}>
              <span>0{index}</span><strong>{title}</strong><small>{detail}</small>
            </li>
          </ol>
        </section>

        <section class="service-offer__part" aria-labelledby="watchdog-rules-title">
          <div>
            <p class="eyebrow">Limits</p>
            <h2 id="watchdog-rules-title">The rules we follow</h2>
          </div>
          <ul class="service-rules">
            <li :for={rule <- @offer.rules}>{rule}</li>
          </ul>
        </section>

        <section class="service-offer__part" aria-labelledby="watchdog-get-title">
          <div>
            <p class="eyebrow">Deliverables</p>
            <h2 id="watchdog-get-title">You get</h2>
          </div>
          <dl class="service-deliverables">
            <div :for={{title, detail} <- @offer.deliverables}>
              <dt>{title}</dt>
              <dd>{detail}</dd>
            </div>
          </dl>
        </section>

        <section class="service-offer__part" aria-labelledby="watchdog-price-title">
          <div>
            <p class="eyebrow">Price</p>
            <h2 id="watchdog-price-title">Cost</h2>
          </div>
          <p>{@offer.price}</p>
        </section>

        <Regent.Structure.panel class="service-offer__start rg-panel__body rg-support-panel">
          <p class="eyebrow">Start</p>
          <h2>Contact</h2>
          <p>{@offer.start_line}</p>
          <a class="rg-button rg-button--primary" href={@mailto}>Email build@regents.sh</a>
        </Regent.Structure.panel>
      </article>
    </Layouts.page>
    """
  end

  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <article class="service-offer" aria-labelledby="service-title">
        <header class="editorial-heading">
          <p class="eyebrow">{@offer.name}</p>
          <h1 id="service-title">{@offer.promise}</h1>
          <p class="lede">{@offer.lede}</p>
          <div class="service-offer__actions">
            <a class="rg-button rg-button--primary" href={@mailto}>Email us</a>
            <a class="text-link" href={@offer.sample_path}>Read the sample report →</a>
          </div>
          <p class="service-offer__other">
            {@offer.other.lead} <a href={@offer.other.path}>{@offer.other.name}</a>.
            For ongoing watching of sites you own, see <a href={~p"/services/watchdog"}>Techtree Watchdog</a>.
          </p>
        </header>

        <section class="service-result" aria-labelledby="service-result-title">
          <%= case @bench do %>
            <% {:ok, figures} -> %>
              <p class="eyebrow">{tested(figures)}</p>
              <h2 id="service-result-title">Wallet Bench</h2>
              <dl class="service-result__figures">
                <div :for={{figure, label} <- bench(figures)}>
                  <dt>{label}</dt>
                  <dd>{figure}</dd>
                </div>
              </dl>
            <% :database_down -> %>
              <p class="eyebrow">Our own bench</p>
              <h2 id="service-result-title">Wallet Bench</h2>
              <p class="empty-state" role="status">
                The bench figures can't be shown right now. Try again in a minute.
              </p>
          <% end %>
          <a class="text-link" href={~p"/wallet-bench"}>See the bench →</a>
        </section>

        <section class="service-offer__part" aria-labelledby="service-get-title">
          <div>
            <p class="eyebrow">Deliverables</p>
            <h2 id="service-get-title">You get</h2>
          </div>
          <dl class="service-deliverables">
            <div :for={{title, detail} <- @offer.deliverables}>
              <dt>{title}</dt>
              <dd>{detail}</dd>
            </div>
          </dl>
        </section>

        <Regent.Structure.panel class="service-offer__flow rg-panel__body">
          <p class="eyebrow">Process</p>
          <ol class="service-flow">
            <li :for={{{stage, title, detail}, index} <- Enum.with_index(@offer.steps, 1)}>
              <span>0{index} / {stage}</span><strong>{title}</strong><small>{detail}</small>
            </li>
          </ol>
        </Regent.Structure.panel>

        <section class="service-offer__part" aria-labelledby="service-sample-title">
          <div>
            <p class="eyebrow">Sample report</p>
            <h2 id="service-sample-title">{@offer.sample_title}</h2>
            <p>{@offer.sample_line}</p>
            <a class="text-link" href={@offer.sample_path}>Read the sample report →</a>
          </div>
          <ul class="service-sample">
            <li :for={{label, result, mark} <- @offer.sample_rows}>
              <span>{label}</span>
              <strong class={["service-sample__mark", "service-sample__mark--#{mark}"]}>
                {result}
              </strong>
            </li>
          </ul>
        </section>

        <Regent.Structure.panel class="service-offer__start rg-panel__body rg-support-panel">
          <p class="eyebrow">Start</p>
          <h2>Contact</h2>
          <p>{@offer.start_line}</p>
          <a class="rg-button rg-button--primary" href={@mailto}>Email build@regents.sh</a>
        </Regent.Structure.panel>
      </article>
    </Layouts.page>
    """
  end
end
