defmodule TechtreeWeb.ServiceLive do
  @moduledoc """
  The two paid offers, Techtree Verify at `/services/verify` and Techtree Cyber
  Assist at `/services/cyber-assist`: the Agent Wallet Bench result first, then
  what the buyer gets, how an engagement runs, a sample of the report and the way
  to start a conversation. Each page's Markdown is
  `priv/public/services/<offer>.md`, the same facts in words, and its sample
  report is a public document (`TechtreeWeb.PublicDocuments`).

  The bench figures are the published scores as read on 28 October 2026.
  """

  use TechtreeWeb, :live_view

  @bench [
    {"12", "coding agents tested"},
    {"35 of 35", "working wallets they set up left their key or unlock password in a plain file"},
    {"4", "safety failures in 85 judged tests"}
  ]

  @offers %{
    verify: %{
      name: "Techtree Verify",
      promise: "Prove your important workflows work.",
      lede:
        "For teams that ship quickly. We check the workflows you choose, reproduce every failure and leave you a suite you can run again.",
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
        "Write to build@regents.sh with what you ship and the workflows that matter most.",
      subject: "Techtree Verify"
    },
    cyber_assist: %{
      name: "Techtree Cyber Assist",
      promise: "Find and fix the security weaknesses that matter.",
      lede:
        "For applications and agent integrations. We validate each weakness, show how to reproduce it, rank the repairs and check that each fix holds.",
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
        "Write to build@regents.sh with what you build and where you want a second look.",
      subject: "Techtree Cyber Assist"
    }
  }

  @impl true
  def mount(_params, _session, socket) do
    offer = Map.fetch!(@offers, socket.assigns.live_action)

    {:ok,
     assign(socket,
       page_title: offer.name,
       offer: offer,
       bench: @bench,
       mailto: "mailto:build@regents.sh?subject=" <> URI.encode(offer.subject)
     )}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <article class="service-offer" aria-labelledby="service-title">
        <header class="editorial-heading">
          <p class="eyebrow">{@offer.name}</p>
          <h1 id="service-title">{@offer.promise}</h1>
          <p class="lede">{@offer.lede}</p>
          <div class="service-offer__actions">
            <a class="rg-button rg-button--primary" href={@mailto}>Start a conversation</a>
            <a class="text-link" href={@offer.sample_path}>Read the sample report →</a>
          </div>
        </header>

        <section class="service-result" aria-labelledby="service-result-title">
          <p class="eyebrow">Our own bench, tests run 7 to 27 October 2026</p>
          <h2 id="service-result-title">Agent Wallet Bench</h2>
          <dl class="service-result__figures">
            <div :for={{figure, label} <- @bench}>
              <dt>{label}</dt>
              <dd>{figure}</dd>
            </div>
          </dl>
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
          <p class="eyebrow">How an engagement runs</p>
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
          <h2>Start a conversation</h2>
          <p>{@offer.start_line}</p>
          <a class="rg-button rg-button--primary" href={@mailto}>Email build@regents.sh</a>
        </Regent.Structure.panel>
      </article>
    </Layouts.page>
    """
  end
end
