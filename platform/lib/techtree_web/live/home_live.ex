defmodule TechtreeWeb.HomeLive do
  @moduledoc """
  The home page, in six parts: the promise with Book Call, naming whose open
  tools the work is built on; the four services as cards with their price
  levels and the tools each uses under their status (`TechtreeWeb.Services`);
  the demonstrations, every published comparison side by side
  (`Techtree.Train.Comparisons`), each with its two figures, its verdict, its
  page and the Skill's own links, whatever the verdict; how a project runs, in
  six steps; the open-source projects we build on, under each maker's logo or
  name, each with what it does in a Techtree job and its status, all drawn
  from `Services.libraries/0` so the two never differ; and Contact: a last
  Book Call, an email and the enquiry form (`TechtreeWeb.Components.Enquiry`),
  whose allowance counts the page's `client_key`.

  The page reads no database; only a sent enquiry writes. The moving parts are
  the hooks in `assets/js/marketing`; every one of them starts from the page as
  the server drew it, which is whole and still. Its Markdown (`markdown/0`) is
  built from the same words and data, so the two never say different things.
  """

  use TechtreeWeb, :live_view

  import TechtreeWeb.Components.Marketing, only: [field: 1, price: 1]

  alias Techtree.Train.Comparisons
  alias TechtreeWeb.Components.{BookCall, Enquiry}
  alias TechtreeWeb.Services
  alias TechtreeWeb.TrainCopy, as: Copy

  @title "Better agents for your business."
  @promise "Skills, evaluations, training environments and open-weight models, built around your " <>
             "workflows on open tools from Prime Intellect, NVIDIA Nemotron, Hugging Face and Harbor, " <>
             "with results you can measure."
  @services_line "Paid custom projects, delivered by people, around the workflows you rely on. " <>
                   "Each uses open tools such as Prime Intellect’s Verifiers and NVIDIA’s " <>
                   "SkillEvaluator, marked Tested once we have run them ourselves."
  @demonstrations_line "Runs Techtree did itself on public Skills, not customer work. Each compares " <>
                         "the Skill as published with the version chosen to improve it, on " <>
                         "final-test cases kept apart from the improvement. A difference within " <>
                         "chance is reported as inconclusive."
  @process_line "Every project runs in the same six steps."
  @process [
    {"Intake", "You bring real examples of the work, and the failures you already know about."},
    {"Success",
     "We agree what better means, how it is scored and the budget cap, before anything runs."},
    {"Baseline",
     "We measure what you run today, several times over, and set the cases for the final test aside."},
    {"Improve",
     "We make one change, to a Skill, an eval, an environment or a model, within the limits agreed up front."},
    {"Final test",
     "One run on cases the work never saw, with everything else held fixed, so the difference is the change."},
    {"Handover",
     "You keep the result, a report of what changed and what it costs to run, and one command that reruns the test."}
  ]
  @stack_line "Each project below is its maker’s own work, with the job it does for Techtree."
  @closing "Tell us about the workflow you want to improve."
  @mailto "mailto:build@regents.sh"

  @impl true
  def mount(_params, %{"client_key" => client_key}, socket) do
    {:ok,
     assign(socket,
       page_title: "Better agents for your business",
       client_key: client_key,
       title: @title,
       promise: @promise,
       services_line: @services_line,
       services: Services.all(),
       comparisons: Comparisons.list(),
       demonstrations_line: @demonstrations_line,
       process_line: @process_line,
       process: @process,
       stack_line: @stack_line,
       status_line: Services.status_line(),
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
          "Price level: #{service.price} of 4. Tools: #{tool_names(service)}"
      end)

    security = Services.security()

    process =
      @process
      |> Enum.with_index(1)
      |> Enum.map_join("\n", fn {{name, line}, index} -> "#{index}. #{name}: #{line}" end)

    makers =
      Enum.map_join(makers(), "\n", fn maker ->
        "- #{maker.name}\n" <>
          Enum.map_join(maker.projects, "\n", fn project ->
            "  - [#{Services.label(project)}](#{project.href}) " <>
              "(#{Services.status_name(project.status)}): #{project.line}"
          end)
      end)

    """
    # Techtree

    #{@title}

    #{@promise} #{BookCall.markdown(@mailto)}

    ## Services

    #{@services_line}

    #{services}
    - [#{security.name}](#{Services.path(:security)}): #{security.promise}
    #{demonstrations_markdown(Comparisons.list())}
    ## Process

    #{@process_line}

    #{process}

    ## Built on

    #{@stack_line} #{Services.status_line()}

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

  defp demonstrations_markdown([]), do: ""

  defp demonstrations_markdown(comparisons) do
    items =
      Enum.map_join(comparisons, "\n", fn comparison ->
        %{final: final, skill: skill} = comparison

        """
        ### #{skill.name}

        #{about(comparison)}

        - Original: #{Copy.percent(final.original)}
        - Revised: #{Copy.percent(final.improved)}
        - Verdict: #{Copy.verdict_name(comparison)}. #{Copy.verdict(comparison)}

        [Result](/train/#{comparison.slug}) · [GitHub](#{skill.github_url}) · [skills.sh](#{skill.skills_sh_url})
        """
      end)

    """

    ## Demonstrations

    #{@demonstrations_line}

    #{items}
    """
  end

  # One demonstration's label: whose public Skill, and the final test's size.
  defp about(%{skill: skill, split: split, repeats: repeats}),
    do:
      "#{skill.maker}’s public Skill, on #{split.final} final-test cases asked #{repeats} times each."

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
              <dl class="mk-service__tools">
                <div :for={{status, tools} <- Services.by_status(service.tools)}>
                  <dt>{Services.status_name(status)}</dt>
                  <dd>
                    <span :for={tool <- tools} class="mk-service__tool">
                      {Services.label(tool)}
                    </span>
                  </dd>
                </div>
              </dl>
              <div class="mk-service__foot">
                <.price level={service.price} />
                <Regent.Icons.icon name="arrow-right" class="mk-service__arrow" />
              </div>
            </div>
          </li>
        </ul>
      </section>

      <section
        :if={@comparisons != []}
        id="demonstration"
        class="mk-section"
        aria-labelledby="demonstration-title"
      >
        <header class="mk-section__head">
          <p class="mk-eyebrow">Skills</p>
          <h2 id="demonstration-title">Demonstrations</h2>
          <p>{@demonstrations_line}</p>
        </header>
        <div id="demonstration-list" class="mk-offer mk-offer--three mk-demos">
          <.demonstration :for={comparison <- @comparisons} comparison={comparison} />
        </div>
      </section>

      <section id="process" class="mk-section" aria-labelledby="process-title">
        <header class="mk-section__head">
          <h2 id="process-title">Process</h2>
          <p>{@process_line}</p>
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
          <h2 id="stack-title">Built on</h2>
          <p>{@stack_line} {@status_line}</p>
        </header>
        <ul id="stack-list" class="mk-stack__list" phx-hook="MarketingStagger" phx-update="ignore">
          <li :for={maker <- @makers} id={"maker-#{maker.id}"} class="mk-maker" data-stagger>
            <h3 :if={maker.logo} class="mk-maker__plate">
              <img
                class={["mk-maker__logo", "mk-maker__logo--#{maker.id}"]}
                src={maker.logo.src}
                alt={maker.name}
                width={maker.logo.width}
                height={maker.logo.height}
              />
            </h3>
            <h3 :if={!maker.logo} class="mk-maker__plate mk-maker__plate--name">{maker.name}</h3>
            <ul class="mk-maker__projects">
              <li :for={project <- maker.projects} data-status={project.status}>
                <span class="mk-maker__name">
                  <a href={project.href} class="text-link">
                    <span><span class="mk-maker__of">{project.maker}’s</span> {project.name}</span>
                  </a>
                  <Regent.Primitives.status tone="neutral" class="mk-status-word">
                    {Services.status_name(project.status)}
                  </Regent.Primitives.status>
                </span>
                <span class="mk-maker__job">{project.line}</span>
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
        <.live_component module={Enquiry} id="enquiry" service={nil} client_key={@client_key} />
      </section>
    </Layouts.page>
    """
  end

  attr :comparison, :map, required: true

  # One demonstration in its one measure: each version's share of attempts
  # solved on the final test, the verdict those figures earn, and its links.
  defp demonstration(assigns) do
    assigns = assign(assigns, about: about(assigns.comparison))

    ~H"""
    <section
      id={"demonstration-#{@comparison.slug}"}
      aria-labelledby={"demonstration-#{@comparison.slug}-title"}
      data-verdict={@comparison.verdict}
    >
      <h3 id={"demonstration-#{@comparison.slug}-title"}>{@comparison.skill.name}</h3>
      <p>{@about}</p>
      <dl
        id={"demonstration-#{@comparison.slug}-figures"}
        class="mk-tallies"
        phx-hook="MarketingTally"
        phx-update="ignore"
      >
        <div>
          <dt>Original</dt>
          <dd data-tally>{Copy.percent(@comparison.final.original)}</dd>
        </div>
        <div>
          <dt>Revised</dt>
          <dd data-tally>{Copy.percent(@comparison.final.improved)}</dd>
        </div>
      </dl>
      <p class="mk-demos__verdict">
        <Regent.Primitives.status
          tone={if(@comparison.verdict == :improved, do: "success", else: "neutral")}
          class="mk-status-word"
        >
          {Copy.verdict_name(@comparison)}
        </Regent.Primitives.status>
        <span>{Copy.verdict(@comparison)}</span>
      </p>
      <p class="mk-links">
        <.link navigate={~p"/train/#{@comparison.slug}"} class="text-link">
          Result <span aria-hidden="true">→</span>
        </.link>
        <a href={@comparison.skill.github_url} class="text-link" rel="noopener">
          GitHub <span aria-hidden="true">↗</span>
        </a>
        <a href={@comparison.skill.skills_sh_url} class="text-link" rel="noopener">
          skills.sh <span aria-hidden="true">↗</span>
        </a>
      </p>
    </section>
    """
  end

  # A service's tools by status, for its line in the Markdown:
  # "Tested: NVIDIA’s SkillEvaluator · Microsoft’s SkillOpt."
  defp tool_names(service) do
    service.tools
    |> Services.by_status()
    |> Enum.map_join(" ", fn {status, tools} ->
      "#{Services.status_name(status)}: #{Enum.map_join(tools, " · ", &Services.label/1)}."
    end)
  end

  # Whose open-source projects we build on, in `Services.libraries/0`'s order:
  # each maker's own logo, unchanged (`priv/static/images/built-on/`), or its
  # name where we have no logo file, over its projects. These are the only
  # logos on the site.
  defp makers do
    Services.libraries()
    |> Enum.chunk_by(& &1.maker)
    |> Enum.map(fn [%{maker: name} | _] = projects ->
      %{
        id: name |> String.downcase() |> String.replace(" ", "-"),
        name: name,
        logo: logo(name),
        projects: projects
      }
    end)
  end

  defp logo("Prime Intellect"),
    do: %{src: ~p"/images/built-on/prime-intellect.svg", width: 899, height: 161}

  defp logo("NVIDIA"), do: %{src: ~p"/images/built-on/nvidia.svg", width: 2560, height: 1440}

  defp logo("Nous Research"),
    do: %{src: ~p"/images/built-on/nous-research.svg", width: 200, height: 280}

  defp logo(_maker), do: nil
end
