defmodule TechtreeWeb.HomeLive do
  @moduledoc """
  The home page, in six parts: the promise with Book Call; the four services
  as cards with their price levels (`TechtreeWeb.Services`); one case study,
  the newest Skill comparison (`Techtree.Train.Comparisons`), with exactly what
  its evidence shows, its page and how to check it; how a project runs, in
  three steps; the open-source projects we build on, under each maker's logo;
  and a last Book Call.

  The page reads no database. The moving parts are the hooks in
  `assets/js/marketing`; every one of them starts from the page as the server
  drew it, which is whole and still. Its Markdown (`markdown/0`) is built from
  the same words and data, so the two never say different things.
  """

  use TechtreeWeb, :live_view

  import TechtreeWeb.Components.Marketing, only: [field: 1, price: 1]

  alias Techtree.Train.Comparisons
  alias TechtreeWeb.Components.BookCall
  alias TechtreeWeb.Services
  alias TechtreeWeb.TrainCopy, as: Copy

  @title "Better agents for your business."
  @promise "Custom Skills, evaluations, training environments, and open-weight models, " <>
             "built around your workflows, with results you can measure."
  @services_line "Paid custom projects, delivered by people, around the workflows you rely on."
  @process [
    {"Agree",
     "You share examples of the work. Together we agree what success means and how it is scored."},
    {"Improve",
     "We measure a baseline first, then improve within the budget and limits agreed up front."},
    {"Prove",
     "The final test runs on cases the work never saw. You receive the Skill, eval, environment or model, with a report of what changed."}
  ]
  @closing "Tell us about the workflow you want to improve."
  @mailto "mailto:build@regents.sh"

  @impl true
  def mount(_params, _session, socket) do
    {:ok,
     assign(socket,
       page_title: "Better agents for your business",
       title: @title,
       promise: @promise,
       services_line: @services_line,
       services: Services.all(),
       case_study: newest_skill_comparison(),
       process: @process,
       makers: makers(),
       closing: @closing,
       mailto: @mailto
     )}
  end

  @doc "The home page as Markdown: the same parts, in the same order."
  @spec markdown() :: String.t()
  def markdown do
    services =
      Enum.map_join(Services.all(), "\n", fn service ->
        "- [#{service.name}](#{Services.path(service.id)}): #{service.promise} " <>
          "Price level: #{service.price} of 4."
      end)

    security = Services.security()

    process =
      @process
      |> Enum.with_index(1)
      |> Enum.map_join("\n", fn {{name, line}, index} -> "#{index}. #{name}: #{line}" end)

    makers =
      Enum.map_join(makers(), "\n", fn maker ->
        "- #{maker.name}: " <>
          Enum.map_join(maker.projects, ", ", fn {name, href} -> "[#{name}](#{href})" end)
      end)

    """
    # Techtree

    #{@title}

    #{@promise} #{BookCall.markdown(@mailto)}

    ## Services

    #{@services_line}

    #{services}
    - [#{security.name}](#{Services.path(:security)}): #{security.promise}
    #{case_study_markdown(newest_skill_comparison())}
    ## Process

    #{process}

    ## Built on the open-source frontier tech of

    #{makers}

    ## Contact

    #{@closing} #{BookCall.markdown(@mailto)}

    ## Pages

    - [Results](/results): published Results and comparisons, each with how to check it.
    - [Docs](/docs): run Techtree locally, check a Result and publish one.
    - [About](/about), [Changelog](/changelog), [Privacy](/privacy) and [Terms](/terms)

    ## Agents

    - [/skill.md](/skill.md): the Techtree skill, for an agent to install.
    - [/agents.md](/agents.md): the agent guide: the release to install and every step.
    - [/llms.txt](/llms.txt): the short start for agents.
    - [/openapi.json](/openapi.json): every public API address, typed.
    - [/sitemap.xml](/sitemap.xml): every public page.
    """
  end

  defp newest_skill_comparison, do: Enum.find(Comparisons.list(), &(&1.change == :skill))

  defp case_study_markdown(nil), do: ""

  defp case_study_markdown(comparison) do
    [without, with] = comparison.arms
    tasks = comparison.environment.task_count

    """

    ## Case study

    #{about(comparison)}

    - Average score without the Skill: #{Copy.percent(without.mean_reward)}
    - Average score with the Skill: #{Copy.percent(with.mean_reward)}
    - Higher-scoring tasks with the Skill: #{comparison.paired.wins} of #{tasks}
    - Tasks fully solved with the Skill: #{with.solved} of #{tasks} (#{without.solved} without it)

    #{Copy.reading(comparison)}

    [Result](/train/#{comparison.slug}) and [how to check it](#{check()}).
    """
  end

  defp about(comparison),
    do:
      "#{comparison.title}: NVIDIA #{comparison.model.family} on #{comparison.environment.task_count} " <>
        "held-out tasks, once without the Skill and once with it, with the same settings on both sides. " <>
        "Finished #{Copy.date(comparison.operational.finished_at)}."

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide flush>
      <section id="hero" class="mk-hero mk-dark" aria-labelledby="hero-title" data-entrance>
        <.field id="hero-field" scene="glow" class="mk-hero__field" />
        <div class="mk-hero__copy">
          <h1 id="hero-title" class="mk-hero__display" phx-update="ignore" data-entrance-display>
            {@title}
          </h1>
          <p class="mk-hero__lede" data-entrance-part>{@promise}</p>
          <div class="mk-hero__actions" data-entrance-part>
            <BookCall.book_call />
            <a href="#services" class="rg-button rg-button--secondary">Services</a>
          </div>
        </div>
      </section>

      <section id="services" class="mk-section" aria-labelledby="services-title">
        <header class="mk-section__head">
          <h2 id="services-title">Services</h2>
          <p>{@services_line}</p>
        </header>
        <ul class="mk-services" phx-hook="MarketingStagger" phx-update="ignore" id="services-list">
          <li
            :for={service <- @services}
            id={"service-#{service.id}"}
            class={"mk-service mk-service--#{service.id}"}
            data-stagger
          >
            <.field id={"service-#{service.id}-field"} scene="backdrop" class="mk-service__field" />
            <div class="mk-service__words">
              <h3>
                <.link navigate={Services.path(service.id)} class="mk-service__link">
                  {service.name}
                </.link>
              </h3>
              <p>{service.promise}</p>
              <div class="mk-service__foot">
                <.price level={service.price} />
                <Regent.Icons.icon name="arrow-right" class="mk-service__arrow" />
              </div>
            </div>
          </li>
        </ul>
      </section>

      <.case_study :if={@case_study} comparison={@case_study} />

      <section id="process" class="mk-section" aria-labelledby="process-title">
        <header class="mk-section__head">
          <h2 id="process-title">Process</h2>
          <p>Each project runs in three steps.</p>
        </header>
        <ol class="mk-sequence" phx-hook="MarketingStagger" phx-update="ignore" id="process-steps">
          <li :for={{{name, line}, index} <- Enum.with_index(@process, 1)} data-stagger>
            <span class="mk-sequence__index">0{index}</span>
            <h3>{name}</h3>
            <p>{line}</p>
          </li>
        </ol>
      </section>

      <section id="stack" class="mk-section mk-stack" aria-labelledby="stack-title">
        <header class="mk-section__head">
          <h2 id="stack-title">
            Built on the <span class="mk-stack__whole">open-source</span> frontier tech of
          </h2>
        </header>
        <ul id="stack-list" class="mk-stack__list" phx-hook="MarketingStagger" phx-update="ignore">
          <li :for={maker <- @makers} class="mk-maker" data-stagger>
            <h3 class="mk-maker__plate">
              <img
                class={["mk-maker__logo", "mk-maker__logo--#{maker.id}"]}
                src={maker.logo}
                alt={maker.name}
                width={maker.width}
                height={maker.height}
              />
            </h3>
            <ul class="mk-maker__projects">
              <li :for={{name, href} <- maker.projects}>
                <a href={href} class="text-link">{name}</a>
              </li>
            </ul>
          </li>
        </ul>
      </section>

      <section id="begin" class="mk-closing mk-dark" aria-labelledby="begin-title">
        <.field id="begin-field" scene="glow" class="mk-closing__field" />
        <div class="mk-closing__copy">
          <h2 id="begin-title">Contact</h2>
          <p class="mk-closing__line">{@closing}</p>
          <div class="mk-hero__actions">
            <BookCall.book_call />
            <a class="rg-button rg-button--secondary" href={@mailto}>Email us</a>
          </div>
        </div>
      </section>
    </Layouts.page>
    """
  end

  attr :comparison, :map, required: true

  # The newest Skill comparison, in its own figures and words: the average
  # score on each side, the tasks it did better on and the tasks it solved.
  defp case_study(assigns) do
    [without, with] = assigns.comparison.arms
    assigns = assign(assigns, without: without, with: with, about: about(assigns.comparison))

    ~H"""
    <section id="case-study" class="mk-section" aria-labelledby="case-study-title">
      <header class="mk-section__head">
        <p class="mk-eyebrow">Skills</p>
        <h2 id="case-study-title">Case study</h2>
        <p>{@about}</p>
      </header>
      <dl
        id="case-study-figures"
        class="mk-tallies"
        phx-hook="MarketingTally"
        phx-update="ignore"
      >
        <div>
          <dt>Average score without the Skill</dt>
          <dd data-tally>{Copy.percent(@without.mean_reward)}</dd>
        </div>
        <div>
          <dt>Average score with the Skill</dt>
          <dd data-tally>{Copy.percent(@with.mean_reward)}</dd>
        </div>
        <div>
          <dt>Higher-scoring tasks with the Skill</dt>
          <dd data-tally>{@comparison.paired.wins} of {@comparison.environment.task_count}</dd>
        </div>
        <div>
          <dt>Tasks fully solved with the Skill ({@without.solved} without it)</dt>
          <dd data-tally>{@with.solved} of {@comparison.environment.task_count}</dd>
        </div>
      </dl>
      <p class="mk-section__note">{Copy.reading(@comparison)}</p>
      <p class="mk-links">
        <.link navigate={~p"/train/#{@comparison.slug}"} class="text-link">
          Result <span aria-hidden="true">→</span>
        </.link>
        <.link navigate={check()} class="text-link">
          How to check it <span aria-hidden="true">→</span>
        </.link>
      </p>
    </section>
    """
  end

  # Where the case study's evidence is explained.
  defp check, do: ~p"/docs/verify" <> "#blog-section-skill-comparisons"

  # Whose open-source projects we build on: each maker's own logo, unchanged
  # (`priv/static/images/built-on/`), over its projects. These are the only
  # logos on the site.
  defp makers do
    [
      %{
        id: "prime-intellect",
        name: "Prime Intellect",
        logo: ~p"/images/built-on/prime-intellect.svg",
        width: 899,
        height: 161,
        projects: [
          # The founder's ruling names Verifiers only with its maker.
          {"Prime Intellect’s Verifiers", "https://github.com/PrimeIntellect-ai/verifiers"},
          {"prime-rl", "https://github.com/PrimeIntellect-ai/prime-rl"},
          {"Environments Hub", "https://app.primeintellect.ai/dashboard/environments"}
        ]
      },
      %{
        id: "nvidia",
        name: "NVIDIA",
        logo: ~p"/images/built-on/nvidia.svg",
        width: 2560,
        height: 1440,
        projects: [
          {"SkillEvaluator", "https://github.com/NVIDIA/SkillEvaluator"},
          {"Skill2Env", "https://github.com/NVlabs/Skill2Env"},
          {"Nemotron", "https://www.nvidia.com/en-us/ai-data-science/foundation-models/nemotron/"}
        ]
      },
      %{
        id: "nous-research",
        name: "Nous Research",
        logo: ~p"/images/built-on/nous-research.svg",
        width: 200,
        height: 280,
        projects: [{"Hermes", "https://github.com/NousResearch/hermes-agent"}]
      }
    ]
  end
end
