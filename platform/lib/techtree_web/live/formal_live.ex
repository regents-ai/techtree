defmodule TechtreeWeb.FormalLive do
  @moduledoc """
  Techtree Formal at `/formal`: what formal verification is, what a proof does
  and doesn't establish, recent advances with their dated sources, a worked
  example (the Wallet Bench funding cap, a Quint model in
  `formal/wallet_bench_funding/`) and how to send code to be proved, an email
  whose body already asks for what we need (`mailto/0`).

  The page's Markdown is `priv/public/formal.md`, the same facts in words; its
  frontier list (`frontier_markdown/0`) and email address are filled in from
  here, so the two never list different advances.
  """

  use TechtreeWeb, :live_view

  @frontier [
    %{
      date: ~D[2026-10-22],
      title: "Crash-free libraries",
      line:
        "Claude wrote proofs, checked by the Rocq proof checker, that 239 entry points in 123 open-source libraries never crash or fail a check on any input under 64 MB, counting the memory errors a standard detector catches. The proofs assume one thread on a model of a RISC-V computer running Linux; hundreds of bugs were found and fixed on the way.",
      source: "Anthropic and Theorem",
      url: "https://www.anthropic.com/research/formal-verification"
    },
    %{
      date: ~D[2026-09-04],
      title: "Fermat in Lean",
      line:
        "Claude, working largely on its own for 11 days, wrote a complete proof of Fermat's Last Theorem, building on Lean's shared maths library, that the Lean proof checker accepts. It checks a known proof; it is not new mathematics.",
      source: "Anthropic",
      url: "https://www.anthropic.com/research/formalizing-fermats-last-theorem"
    },
    %{
      date: ~D[2025-11-21],
      title: "AI Composer",
      line:
        "Certora released an early, open-source tool that checks AI-written smart contract code against safety rules with its Prover while the code is being written.",
      source: "Certora",
      url: "https://www.certora.com/blog/certora-ai-composer-first-safe-ai-coding-platform"
    },
    %{
      date: ~D[2025-11-17],
      title: "Specs for AI code",
      line:
        "Informal Systems had an AI update a Quint model of a consensus protocol, checked the model by hand and by machine, then had the AI write the code and tests from it, with people guiding the design. One case study; the authors say the process has much to mature.",
      source: "Quint",
      url: "https://quint-lang.org/posts/llm_era"
    },
    %{
      date: ~D[2025-11-12],
      title: "AlphaProof",
      line:
        "Google DeepMind published how AlphaProof learns to find Lean proofs by practising on millions of problems. With AlphaGeometry 2 it reached a silver-medal score at the 2024 International Mathematical Olympiad.",
      source: "Nature",
      url: "https://www.nature.com/articles/s41586-025-09833-y"
    },
    %{
      date: ~D[2025-10-01],
      title: "Aristotle",
      line:
        "Harmonic's Aristotle gave Lean-checked solutions to five of the six 2025 International Mathematical Olympiad problems, a gold-medal-equivalent result.",
      source: "Harmonic",
      url: "https://arxiv.org/abs/2510.01346"
    },
    %{
      date: ~D[2025-08-06],
      title: "Checked answers",
      line:
        "Automated Reasoning checks in Amazon Bedrock became generally available. They use mathematical logic to check that an AI model's answers follow a set of written rules.",
      source: "AWS",
      url:
        "https://aws.amazon.com/about-aws/whats-new/2025/08/automated-reasoning-checks-amazon-bedrock-guardrails/"
    },
    %{
      date: ~D[2025-07-14],
      title: "Halmos invariants",
      line:
        "Halmos 0.3.0 from a16z checks that a rule, written as a Solidity test, holds across every sequence of smart contract calls up to a set length (two calls by default).",
      source: "a16z",
      url: "https://a16zfrontier.com/posts/article/halmos-v0-3-0-release-highlights/"
    },
    %{
      date: ~D[2024-05-16],
      title: "Kontrol in CI",
      line:
        "Runtime Verification used Kontrol to prove that Optimism's bridge contracts on Ethereum stop processing withdrawals while paused, and added the proofs to Optimism's automatic checks.",
      source: "Runtime Verification",
      url:
        "https://runtimeverification.com/blog/kontrol-integrated-verification-of-the-optimism-pausability-mechanism"
    }
  ]

  @example_url "https://github.com/regents-ai/techtree/tree/main/formal/wallet_bench_funding"
  @subject "Techtree Formal"
  @body ["Company:", "Code:", "Property to prove:", "Where it runs:"]

  @impl true
  def mount(_params, _session, socket) do
    {:ok,
     assign(socket,
       page_title: "Techtree Formal",
       frontier: @frontier,
       example_url: @example_url,
       mailto: mailto()
     )}
  end

  @doc "The email the page starts: to build@regents.sh, with its subject and the lines its body asks for."
  @spec mailto() :: String.t()
  def mailto do
    query = URI.encode_query([subject: @subject, body: Enum.join(@body, "\r\n")], :rfc3986)
    "mailto:build@regents.sh?" <> query
  end

  @doc "The frontier list as Markdown, newest first, each advance with its date and source."
  @spec frontier_markdown() :: String.t()
  def frontier_markdown do
    Enum.map_join(@frontier, "\n", fn item ->
      "- **#{item.title}** (#{date(item.date)}). #{item.line} [#{item.source}](#{item.url})"
    end)
  end

  @doc "Where the worked example's files are."
  @spec example_url() :: String.t()
  def example_url, do: @example_url

  defp date(day), do: Calendar.strftime(day, "%-d %B %Y")

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <article class="formal" aria-labelledby="formal-title">
        <header class="editorial-heading">
          <p class="service-kicker">
            <span class="eyebrow">Techtree Formal</span>
            <Regent.Primitives.status tone="warning" class="badge">
              Experimental
            </Regent.Primitives.status>
          </p>
          <h1 id="formal-title">Formal Verification</h1>
          <p class="lede">
            A proof shows that a precise model of the code keeps a stated property for every input the model allows, not only the inputs a test tried, and a computer checks every step.
          </p>
          <div class="service-offer__actions">
            <a class="rg-button rg-button--primary" href={@mailto}>Email us</a>
            <a class="text-link" href="#formal-example-title">See the example →</a>
          </div>
        </header>

        <section class="service-offer__part" aria-labelledby="formal-basics-title">
          <div>
            <p class="eyebrow">Plain words</p>
            <h2 id="formal-basics-title">Basics</h2>
            <p>
              A test tries the inputs someone picked. A proof covers every input the model allows.
            </p>
          </div>
          <dl class="service-deliverables">
            <div>
              <dt>Property</dt>
              <dd>The rule you need, such as "the total paid never passes the cap".</dd>
            </div>
            <div>
              <dt>Model</dt>
              <dd>A precise description of the code, or of its design, that the proof is about.</dd>
            </div>
            <div>
              <dt>Proof</dt>
              <dd>A step-by-step argument that a small checker program accepts.</dd>
            </div>
          </dl>
        </section>

        <section class="service-offer__part" aria-labelledby="formal-limits-title">
          <div>
            <p class="eyebrow">Honest scope</p>
            <h2 id="formal-limits-title">Limits</h2>
            <p>
              A proof covers the property as written and the model as built, under the assumptions it states.
            </p>
          </div>
          <ul class="formal-limits">
            <li>A property that misses the point gives a sound proof of the wrong thing.</li>
            <li>
              Anything outside the model, such as the compiler, the chip, other services or the people calling the code, is assumed, not proven.
            </li>
            <li>A proof about the design says nothing about whether the code follows it.</li>
            <li>
              In Anthropic's words, “Formally verified” does not mean “bug-free.”
              <a href="https://www.anthropic.com/research/formal-verification">Source</a>
            </li>
          </ul>
        </section>

        <section class="formal-frontier" aria-labelledby="formal-frontier-title">
          <p class="eyebrow">Recent advances</p>
          <h2 id="formal-frontier-title">Frontier</h2>
          <ol class="formal-frontier__list">
            <li :for={item <- @frontier}>
              <time datetime={Date.to_iso8601(item.date)}>{date(item.date)}</time>
              <div>
                <strong>{item.title}</strong>
                <p>{item.line}</p>
                <a class="text-link" href={item.url}>{item.source} →</a>
              </div>
            </li>
          </ol>
        </section>

        <section class="service-offer__part" aria-labelledby="formal-example-title">
          <div>
            <p class="service-kicker">
              <span class="eyebrow">Worked example</span>
              <Regent.Primitives.status tone="neutral" class="badge">
                In progress
              </Regent.Primitives.status>
            </p>
            <h2 id="formal-example-title">Funding Cap</h2>
            <p>
              The Wallet Bench pays each agent it tests a small amount of USDC, and ETH for fees. This model describes how those payments stay within each run's total while several tests run at once, a failed try is retried, or a payment's result on Base is not known yet.
            </p>
            <a class="text-link" href={@example_url}>See the files on GitHub →</a>
          </div>
          <dl class="service-deliverables">
            <div>
              <dt>Property</dt>
              <dd>
                For each token, the payments counted, and the money that really moves on Base, never pass the run's total.
              </dd>
            </div>
            <div>
              <dt>Model</dt>
              <dd>
                The design of the funding step, written in Quint, not the code itself. It assumes Base never undoes a payment it has included, and that reads from Base agree.
              </dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>The model is still being written, so no result is claimed yet.</dd>
            </div>
          </dl>
        </section>

        <Regent.Structure.panel class="service-offer__start rg-panel__body rg-support-panel">
          <p class="eyebrow">Submit</p>
          <h2>Submit Code</h2>
          <ul class="formal-send">
            <li>The code, or a link to its repository.</li>
            <li>The property you need guaranteed, in plain words.</li>
            <li>Where it runs, such as a chain, a server or a device.</li>
          </ul>
          <p>
            We reply by email with a scoped quote. The work is paid, and the price is set once the scope is agreed.
          </p>
          <a class="rg-button rg-button--primary" href={@mailto}>Email build@regents.sh</a>
        </Regent.Structure.panel>
      </article>
    </Layouts.page>
    """
  end
end
