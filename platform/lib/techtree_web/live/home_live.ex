defmodule TechtreeWeb.HomeLive do
  @moduledoc """
  The home page. A dark opening with the promise, Start, Book Call, one
  copyable instruction for an agent and the newest published Results turning
  in a row; the projects Techtree is built on (`TechtreeWeb.SiteMenu.stack/0`),
  under each maker's logo;
  the site's figures; Evaluate & Climb, the core of Techtree, as two steps of
  small moving cards; the six products as cards; the products in three groups
  (Measure, Prove, Build), each beside a moving dot picture; a dark band with
  the path from a team's own work through Techtree to Prime Intellect, and a
  way to get in touch; the three services; what an agent can use; what works
  today and what Techtree keeps; the newest news; and a last Start.

  The moving parts are the hooks in `assets/js/marketing`. Every one of them
  starts from the page as the server drew it, which is whole and still.
  """

  use TechtreeWeb, :live_view

  import TechtreeWeb.Components.ValueCards

  alias Techtree.Catalog.Query
  alias Techtree.Network.Query, as: Results
  alias Techtree.Network.Verdict
  alias Techtree.Train.Comparisons
  alias Techtree.WalletBench.Catalog, as: WalletCatalog
  alias TechtreeWeb.CampaignFacts
  alias TechtreeWeb.Capabilities
  alias TechtreeWeb.ClimbCopy
  alias TechtreeWeb.Components.BookCall
  alias TechtreeWeb.News
  alias TechtreeWeb.Outage
  alias TechtreeWeb.ReleaseInfo
  alias TechtreeWeb.ResultAssessment
  alias TechtreeWeb.ResultNames
  alias TechtreeWeb.SiteMenu
  alias TechtreeWeb.WalletBenchScores

  # How many published Results the opening turns through.
  @shown_results 5
  # The most squares the Live run card draws for the newest Result's tasks.
  @most_cells 24
  # Techtree's mark, the thirteen squares of its canopy, by column and row.
  @mark for row <- 0..2, column <- 0..4, row > 0 or rem(column, 2) == 0, do: {column, row}

  @impl true
  def mount(_params, _session, socket) do
    {release, climbs, results, figures, catalog} =
      case Outage.read(fn ->
             climbs = Query.list_climbs()

             {ReleaseInfo.current(), climbs, results(Results.standing(@shown_results)),
              figures(climbs)}
           end) do
        {:ok, {release, climbs, results, figures}} -> {release, climbs, results, figures, :read}
        :database_down -> {nil, [], [], [], :unreadable}
      end

    campaign = release && Enum.find(climbs, &(&1.reference == release.introductory_reference))
    newest = List.first(results)

    {:ok,
     assign(socket,
       page_title: "Improve a Skill. Prove it worked.",
       agent_line: agent_line(),
       news: News.latest(3),
       results: results,
       newest: newest,
       cells: cells(newest),
       figures: figures,
       campaign: campaign,
       campaign_copy: campaign && ClimbCopy.for_reference(campaign.reference),
       campaign_facts: CampaignFacts.for_climb(campaign),
       climbs: Enum.map(climbs, &{&1, ClimbCopy.for_reference(&1.reference)}),
       capabilities: Capabilities.all(),
       products: products(),
       tasksmith: climb_with_slug(climbs, "tasksmith-climb"),
       frontier: climb_with_slug(climbs, "frontier-cs-open-ended-climb"),
       wallet_harnesses:
         names(
           Enum.filter(WalletCatalog.harness_ids(), &(:T2 in WalletCatalog.tests(&1))),
           &WalletCatalog.harness!/1
         ),
       wallet_tools: names(WalletCatalog.tested_wallet_ids(), &WalletCatalog.wallet!/1),
       site_tools:
         for(
           tool <- Techtree.Capabilities.site_tools(),
           tool["requires"] == "none",
           do: tool["title"]
         ),
       release: release,
       catalog: catalog
     )}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide flush>
      <section id="hero" class="mk-hero mk-dark" aria-labelledby="hero-title" data-entrance>
        <.field id="hero-field" scene="glow" class="mk-hero__field" />

        <div class="mk-hero__copy">
          <a :if={@news != []} href={hd(@news).href} class="mk-pill" data-entrance-news>
            <span class="mk-pill__tag">New</span>
            <span class="mk-pill__words">{hd(@news).title}</span>
            <Regent.Icons.icon name="arrow-right" class="mk-pill__arrow" />
          </a>
          <h1 id="hero-title" class="mk-hero__name">Techtree</h1>
          <p id="hero-display" class="mk-hero__display" phx-update="ignore" data-entrance-display>
            <span>Improve a Skill.</span> <span>Prove it worked.</span>
          </p>
          <p class="mk-hero__lede" data-entrance-part>
            Evaluate &amp; Climb runs your agent on the same tasks with and without your Skill,
            shows what improved and what regressed, and keeps a signed Result anyone can check.
          </p>
          <div class="mk-hero__actions" data-entrance-part>
            <.link navigate={~p"/start"} class="rg-button rg-button--primary">Start</.link>
            <BookCall.book_call variant={:secondary} />
          </div>
          <p class="mk-hero__built" data-entrance-part>
            Every Climb is scored by <a href="https://github.com/PrimeIntellect-ai/verifiers">Prime Intellect’s Verifiers</a>.
            Skill checks from
            <a href="https://github.com/NVIDIA/SkillEvaluator">NVIDIA’s SkillEvaluator</a>
            are coming soon.
          </p>
          <div class="mk-hero__prompt" data-entrance-part>
            <.prompt_block id="copy-home-agent-line" label="Agent prompt" text={@agent_line} />
          </div>
        </div>

        <.carousel :if={@results != []} results={@results} />
      </section>

      <section id="stack" class="mk-section mk-stack" aria-labelledby="stack-title">
        <header class="mk-section__head">
          <h2 id="stack-title">
            Built on the <span class="mk-stack__whole">open-source</span> frontier tech of
          </h2>
        </header>
        <ul
          id="stack-list"
          class="mk-stack__list"
          phx-hook="MarketingStagger"
          phx-update="ignore"
        >
          <li
            :for={projects <- Enum.chunk_by(SiteMenu.stack().pages, & &1.by)}
            class="mk-maker"
            data-stagger
          >
            <h3 class="mk-maker__plate">
              <.maker_logo by={hd(projects).by} />
            </h3>
            <ul class="mk-maker__projects">
              <li :for={project <- projects}>
                <a href={project.href} class="mk-tile">
                  <span class="mk-tile__by">{project.by}</span>
                  <span class="mk-tile__name">
                    {project.name} <span :if={project.soon} class="mk-soon">Soon</span>
                  </span>
                  <span class="mk-tile__line">{project.line}</span>
                  <Regent.Icons.icon name="arrow-up-right" class="mk-tile__arrow" />
                </a>
              </li>
            </ul>
          </li>
          <li>
            <a href="#onramp" class="mk-tile mk-tile--path mk-dark" data-stagger>
              <span class="mk-tile__by">Techtree</span>
              <span class="mk-tile__name">On-ramp</span>
              <span class="mk-tile__line">From your Skill to Prime Intellect</span>
              <Regent.Icons.icon name="arrow-down" class="mk-tile__arrow" />
            </a>
          </li>
        </ul>
      </section>

      <section
        :if={@figures != []}
        id="figures"
        class="mk-figures"
        aria-label="Figures"
        phx-hook="MarketingTally"
      >
        <ul class="mk-figures__list">
          <li :for={figure <- @figures}>
            <a href={figure.href} class="mk-figure">
              <span class="mk-figure__value" data-tally>{figure.value}</span>
              <span class="mk-figure__label">{figure.label}</span>
            </a>
          </li>
        </ul>
      </section>

      <section
        id="evaluate"
        class="mk-section mk-statement"
        aria-labelledby="evaluate-title"
        phx-hook="MarketingCards"
      >
        <header class="mk-section__head">
          <p class="mk-eyebrow">Core</p>
          <h2 id="evaluate-title" phx-hook="MarketingRise" phx-update="ignore">
            Evaluate &amp; Climb
          </h2>
          <p class="mk-statement__line">
            Evaluate a Skill, then climb: improve it, and prove the gain with a Result anyone can
            check.
          </p>
          <p class="mk-statement__credit">
            The approach follows NVIDIA’s open-source <a href="https://github.com/NVIDIA/SkillEvaluator">SkillEvaluator</a>: check a Skill
            first, then compare live runs with and without it. Its quality and overlap checks are
            coming to Techtree soon.
          </p>
        </header>

        <div class="mk-step">
          <div class="mk-step__head">
            <p class="mk-step__index">01</p>
            <h3>Evaluate</h3>
            <p>Check the Skill, then compare runs with and without it.</p>
          </div>
          <ul class="mk-cards" aria-label="Evaluate">
            <li class="mk-card" data-loop="validate">
              <div class="mk-card__picture mk-file" aria-hidden="true">
                <span class="mk-file__name">SKILL.md</span>
                <span :for={_line <- 1..6} class="mk-file__line" data-line></span>
                <span class="mk-file__sweep" data-sweep></span>
              </div>
              <div class="mk-card__head">
                <h4>Validate</h4>
                <span class="mk-soon">Soon</span>
              </div>
              <p>Is the Skill safe and well written?</p>
            </li>
            <li class="mk-card" data-loop="deduplicate">
              <div class="mk-card__picture mk-copies" aria-hidden="true">
                <span
                  :for={side <- ["left", "right"]}
                  class={"mk-copies__copy mk-copies__copy--#{side}"}
                  data-copy={side}
                >
                  <span class="mk-copies__line"></span>
                  <span class="mk-copies__line" data-repeat></span>
                  <span class="mk-copies__line"></span>
                  <span class="mk-copies__line" data-repeat></span>
                </span>
              </div>
              <div class="mk-card__head">
                <h4>Deduplicate</h4>
                <span class="mk-soon">Soon</span>
              </div>
              <p>Does its guidance repeat itself?</p>
            </li>
            <li class="mk-card" data-loop="runs">
              <div class="mk-card__picture mk-cells" aria-hidden="true">
                <span :for={cell <- @cells} class={"mk-cell mk-cell--#{cell}"} data-cell={cell}></span>
              </div>
              <div class="mk-card__head">
                <h4>Live run</h4>
                <.capability_status capability={:skill_test} />
              </div>
              <p>Does the Skill help the agent?</p>
              <p :if={@newest} class="mk-card__fact">
                Newest Result: <span>{@newest.entry.wins}</span>
                better, <span>{@newest.entry.ties}</span>
                same, <span>{@newest.entry.losses}</span>
                worse.
              </p>
            </li>
          </ul>
        </div>

        <div class="mk-step">
          <div class="mk-step__head">
            <p class="mk-step__index">02</p>
            <h3>Climb</h3>
            <p>Improve the Skill, and prove the gain with a Result anyone can check.</p>
          </div>
          <ul class="mk-cards mk-cards--two" aria-label="Climb">
            <li class="mk-card" data-loop="verdict" data-angle={@newest && angle(@newest.verdict)}>
              <div class="mk-card__picture mk-dial" aria-hidden="true">
                <svg viewBox="0 0 120 68" aria-hidden="true">
                  <path class="mk-dial__arc mk-dial__arc--worse" d="M12 60A48 48 0 0 1 36 18.43" />
                  <path class="mk-dial__arc mk-dial__arc--same" d="M36 18.43A48 48 0 0 1 84 18.43" />
                  <path class="mk-dial__arc mk-dial__arc--better" d="M84 18.43A48 48 0 0 1 108 60" />
                  <path class="mk-dial__ticks" d="M18.4 36 26 40.4M60 12v8.8M101.6 36 94 40.4" />
                  <line
                    class={["mk-dial__needle", @newest && "mk-dial__needle--#{@newest.verdict}"]}
                    data-needle
                    x1="60"
                    y1="60"
                    x2="60"
                    y2="22"
                  />
                  <circle class="mk-dial__hub" cx="60" cy="60" r="4" />
                </svg>
              </div>
              <div class="mk-card__head">
                <h4>Verdict</h4>
              </div>
              <p :if={@newest}>
                Newest Result: {ResultAssessment.label(@newest.verdict)}.
              </p>
              <p :if={!@newest}>Improved, regressed, or too close to call.</p>
            </li>
            <li class="mk-card" data-loop="checks">
              <ul class="mk-card__picture mk-checklist">
                <li
                  :for={
                    line <- [
                      "Signatures verify",
                      "Files match",
                      "Verdict recomputes",
                      "Only the Skill differs"
                    ]
                  }
                  data-check-line
                >
                  <svg viewBox="0 0 16 16" aria-hidden="true">
                    <path data-check d="M3 8.5 6.5 12 13 4.5" />
                  </svg>
                  {line}
                </li>
              </ul>
              <div class="mk-card__head">
                <h4>Offline check</h4>
              </div>
              <p>Check any Result on your own computer.</p>
            </li>
          </ul>
        </div>
      </section>

      <section id="products" class="mk-section" aria-labelledby="products-title">
        <header class="mk-section__head mk-section__head--row">
          <h2 id="products-title">Products</h2>
        </header>
        <.value_cards id="cards-row" label="Products" cards={@products} />
      </section>

      <.group
        id="measure"
        name="Measure"
        line="See what a Skill, an agent or a model change really does."
      >
        <:item title="Evaluate & Climb" icon="mountain" shape={8} capability={:skill_test} open>
          <p>
            Techtree makes practice tasks from what your Skill teaches, following <a href="https://github.com/NVlabs/Skill2Env">NVIDIA’s Skill2Env</a>. Your agent then
            works the same tasks twice: once without the Skill, or with its earlier version, and
            once with it. The model, the tools and the limits stay the same, so any difference
            comes from the Skill.
          </p>
          <p>
            In a Climb,
            <a href="https://github.com/PrimeIntellect-ai/verifiers">Prime Intellect’s Verifiers</a>
            scores every task by its own rules, the same way on both sides. Checks from
            <a href="https://github.com/NVIDIA/SkillEvaluator">NVIDIA’s SkillEvaluator</a>
            are coming soon: whether the Skill is safe and well written, and whether its guidance
            repeats itself.
          </p>
          <p>
            Some tasks are held out from anyone improving the Skill. Their result is the one to
            trust when you ask “should I keep this change?”, because no revision could have
            studied them.
          </p>
          <ol class="mk-flow" aria-label="How a Skill is tested">
            <li><span>01</span> Tasks made from your Skill, and you keep the ones that work</li>
            <li><span>02</span> Run without the Skill or its earlier version, then with it</li>
            <li>
              <span>03</span> Held-out tasks decide: improved, regressed, mixed or no difference
            </li>
          </ol>
          <p class="mk-links">
            <.link navigate={~p"/start"} class="rg-button rg-button--secondary">Start</.link>
            <.link navigate={~p"/start#skill"} class="text-link">
              Test your Skill <span aria-hidden="true">→</span>
            </.link>
            <.link navigate={~p"/examples/tdd"} class="text-link">
              See a real comparison <span aria-hidden="true">→</span>
            </.link>
          </p>
        </:item>
        <:item title="Example" icon="play" shape={2} capability={:climb}>
          <p>
            The Hello World Climb ships with every release: a small, fixed set of tasks run once
            without a starter Skill and once with it. It shows how a run is approved, what it
            records and what a Result looks like. Its toy tasks say nothing about your own Skill.
          </p>
          <p :if={@campaign}>
            It is
            <strong>{@campaign.title}</strong><span :if={@campaign_copy}>, {@campaign_copy.introduction}</span>.
          </p>
          <dl :if={@campaign} class="mk-facts">
            <div>
              <dt>Tasks</dt>
              <dd>{CampaignFacts.membership_words(@campaign_facts.membership) || "Not published"}</dd>
            </div>
            <div>
              <dt>Agent</dt>
              <dd>
                {@campaign.projection["subject_harness"]}
                {@campaign.projection["subject_harness_version"]}
              </dd>
            </div>
            <div>
              <dt>Checked</dt>
              <dd>{CampaignFacts.validation_words(@campaign_facts.validation) || "Not published"}</dd>
            </div>
          </dl>
          <p class="mk-links">
            <.link navigate={~p"/start#example"} class="text-link">
              Try the example <span aria-hidden="true">→</span>
            </.link>
            <a :if={@campaign} class="text-link" href={~p"/climbs/#{@campaign.projection["slug"]}"}>
              Inspect the Climb <span aria-hidden="true">→</span>
            </a>
            <a class="text-link" href={~p"/results"}>
              Published Results <span aria-hidden="true">→</span>
            </a>
          </p>
        </:item>
        <:item
          :if={@climbs != [] or @catalog == :unreadable}
          id="climbs"
          title="Climbs"
          icon="list"
          shape={5}
        >
          <p :if={@catalog == :unreadable} class="empty-state" role="status">
            The Climbs can't be shown right now. Try again in a minute.<br />
            <.link navigate={~p"/docs"}>Read the guide meanwhile</.link>
          </p>
          <ul :if={@climbs != []} class="mk-climbs">
            <li :for={{climb, copy} <- @climbs}>
              <a class="text-link" href={~p"/climbs/#{climb.projection["slug"]}"}>{climb.title}</a>
              <p :if={copy}>{copy.scope}</p>
            </li>
          </ul>
        </:item>
        <:item id="wallet-bench" title="Wallet Bench" icon="wallet" shape={7}>
          <p>
            Can a coding agent set up a wallet safely? AgentWalletBench gives one a clean computer
            and asks it to install a wallet tool from the tool’s own page, set up a wallet it
            controls, say how its keys are kept, and prove control with a signature.
          </p>
          <p>
            Everything the agent does is recorded, with secrets blanked before anything is kept. A
            judge model rules on each answer, and the bench checks any address and signature on
            Base itself. Use it to see which agents and wallet tools work together before you
            trust one with money. We can also check your own agent’s wallet flow.
          </p>
          <dl class="mk-facts">
            <div>
              <dt>Agents</dt>
              <dd>{Enum.join(@wallet_harnesses, ", ")}</dd>
            </div>
            <div>
              <dt>Wallet tools</dt>
              <dd>{Enum.join(@wallet_tools, ", ")}</dd>
            </div>
            <div>
              <dt>Each test</dt>
              <dd>Starts from the same identical cloud server on Fly.io Sprites</dd>
            </div>
          </dl>
          <p class="mk-links">
            <.link navigate={~p"/wallet-bench"} class="text-link">
              See the wallet tests <span aria-hidden="true">→</span>
            </.link>
            <.link navigate={~p"/services/verify"} class="text-link">
              Techtree Verify <span aria-hidden="true">→</span>
            </.link>
          </p>
        </:item>
        <:item title="Train" icon="trending-up" shape={1}>
          <p>
            See NVIDIA Nemotron models scored by Prime Intellect’s Verifiers before and after one
            change, on the same held-out tasks with the same settings.
          </p>
          <p class="mk-links">
            <.link navigate={~p"/train"} class="text-link">
              See the comparisons <span aria-hidden="true">→</span>
            </.link>
          </p>
        </:item>
      </.group>

      <.group
        id="prove"
        name="Prove"
        line="Every Result is signed, so you can check it yourself instead of taking our word."
        flip
      >
        <:item title="Offline check" icon="badge-check" shape={3} open>
          <p>
            Download a signed Result and check it on your own computer, without trusting this
            site: its signatures, its files, its verdict and the one setting its two runs differ
            in.
          </p>
          <p class="mk-links">
            <.link navigate={~p"/verify"} class="text-link">
              Check a Result <span aria-hidden="true">→</span>
            </.link>
          </p>
        </:item>
        <:item title="Results" icon="list-checks" shape={0}>
          <p>
            Every published Result, newest first: the same agent on the same tasks, with and
            without a Skill.
          </p>
          <p class="mk-links">
            <.link navigate={~p"/results"} class="text-link">
              See every Result <span aria-hidden="true">→</span>
            </.link>
          </p>
        </:item>
        <:item title="Formal" icon="sigma" shape={4}>
          <p>
            What a formal proof shows and what it doesn’t, recent advances with their sources, and
            how to send code to be proved.
          </p>
          <p class="mk-links">
            <.link navigate={~p"/formal"} class="text-link">
              Techtree Formal <span aria-hidden="true">→</span>
            </.link>
          </p>
        </:item>
      </.group>

      <.group
        id="build"
        name="Build"
        line="Turn know-how and real work into tasks agents can practice on, then see what helps."
      >
        <:item title="Skill2Env" icon="git-fork" shape={6} capability={:skill_test} open>
          <p>
            Turns a Skill, the know-how written down for an agent, into a set of practice tasks
            with checks. Techtree reads the Skill without running it, plans tasks with you, builds
            and checks them on your computer, and you accept the final set.
          </p>
          <p>
            The task set is useful on its own: you can keep it, export it, or hand it to someone
            else to run, whether or not you go on to compare anything.
          </p>
          <p class="mk-links">
            <.link navigate={~p"/start#skill"} class="text-link">
              Test a Skill <span aria-hidden="true">→</span>
            </.link>
            <a class="text-link" href="https://github.com/NVlabs/Skill2Env">
              NVIDIA’s Skill2Env <span aria-hidden="true">→</span>
            </a>
          </p>
        </:item>
        <:item title="Repo2RLEnv" icon="git-branch" shape={7} capability={:hosted_building}>
          <p>
            Turns a real repository and its history of fixes into practice environments, each one
            a past problem with a known good answer. Real bugs that were really fixed make
            realistic practice, and their own tests say whether an agent got it right.
          </p>
          <p class="mk-links">
            <.link navigate={~p"/repo2rlenv"} class="text-link">
              About Repo2RLEnv <span aria-hidden="true">→</span>
            </.link>
          </p>
        </:item>
        <:item title="Tasksmith" icon="hammer" shape={2}>
          <p>
            The HF ML Tasksmith collection packages real changes to Hugging Face’s
            machine-learning libraries as tasks. Techtree’s Tasksmith Climb uses six of them to
            ask whether adding the Tasksmith Skill solves more: a ready-made test on serious code.
            Each run installs them from Prime Intellect’s Environments Hub.
          </p>
          <p class="mk-links">
            <a :if={@tasksmith} class="text-link" href={~p"/climbs/tasksmith-climb"}>
              The Tasksmith Climb <span aria-hidden="true">→</span>
            </a>
            <a class="text-link" href="https://huggingface.co/datasets/FineEnvs/HF_ML_Tasksmith">
              The collection on Hugging Face <span aria-hidden="true">→</span>
            </a>
          </p>
        </:item>
        <:item title="FrontierSmith" icon="infinity" shape={8} capability={:frontier_climb}>
          <p>
            Writes open-ended programming problems, each with its own checker that scores an
            answer from 0 to 1 rather than simply right or wrong. Techtree’s Frontier-CS Climb
            uses ten problems made with it, so a better score means better work, and partial
            credit shows small gains a pass-or-fail test would miss.
          </p>
          <p class="mk-links">
            <a :if={@frontier} class="text-link" href={~p"/climbs/frontier-cs-open-ended-climb"}>
              The Frontier-CS Climb <span aria-hidden="true">→</span>
            </a>
            <a class="text-link" href="https://github.com/FrontierCS/FrontierSmith">
              FrontierSmith <span aria-hidden="true">→</span>
            </a>
          </p>
        </:item>
      </.group>

      <section id="onramp" class="mk-band mk-dark" aria-labelledby="onramp-title">
        <.field id="onramp-field" scene="mark" class="mk-band__field" />
        <div class="mk-band__copy">
          <h2 id="onramp-title">On-ramp</h2>
          <p class="mk-band__line">
            Techtree is where a team starts. We do the first steps with you: check the Skill,
            build the practice tasks and a fair test, and prove the result.
          </p>
          <p class="mk-band__more">
            Climbs run on Prime Intellect’s Verifiers, which Prime Intellect’s own training uses
            too, so what you leave with is ready to take to Prime Intellect for training and
            environments at scale. We work with smaller teams on these first steps.
          </p>
          <div class="mk-band__actions">
            <BookCall.book_call />
            <a class="rg-button rg-button--secondary" href="mailto:build@regents.sh">Email us</a>
          </div>
        </div>
        <ol
          id="onramp-path"
          class="mk-path"
          aria-label="From your work to training at scale"
          phx-hook="MarketingDraw"
          phx-update="ignore"
        >
          <li class="mk-path__stop">
            <span class="mk-path__badge" aria-hidden="true">
              <Regent.Icons.icon name="folder-git-2" />
            </span>
            <h3>Your work</h3>
            <p>A Skill, or a repository and its history of fixes.</p>
          </li>
          <li class="mk-path__stop mk-path__stop--techtree">
            <span class="mk-path__link" data-link aria-hidden="true">
              <span class="mk-path__pulse"></span>
            </span>
            <span class="mk-path__badge mk-mark" aria-hidden="true">
              <svg viewBox="-1 -1 60 36" aria-hidden="true">
                <rect
                  :for={{column, row} <- mark()}
                  class="mk-mark__outline"
                  data-outline
                  data-col={column}
                  data-row={row}
                  x={column * 12}
                  y={row * 12}
                  width="10"
                  height="10"
                />
                <rect
                  :for={{column, row} <- mark()}
                  class="mk-mark__block"
                  data-block
                  data-col={column}
                  data-row={row}
                  x={column * 12 + 2}
                  y={row * 12 + 2}
                  width="6"
                  height="6"
                />
              </svg>
            </span>
            <h3>Techtree</h3>
            <p>Evaluate the Skill, build the tasks and the fair test, prove the gain.</p>
          </li>
          <li class="mk-path__stop">
            <span class="mk-path__link" data-link aria-hidden="true">
              <span class="mk-path__pulse"></span>
            </span>
            <span class="mk-path__badge" aria-hidden="true">
              <Regent.Icons.icon name="cpu" />
            </span>
            <h3>Prime Intellect</h3>
            <p>Training and environments at scale.</p>
            <a class="mk-path__more" href="https://www.primeintellect.ai/">
              primeintellect.ai <Regent.Icons.icon name="arrow-up-right" />
            </a>
          </li>
        </ol>
      </section>

      <section id="services" class="mk-section" aria-labelledby="services-title">
        <header class="mk-section__head">
          <h2 id="services-title">Services</h2>
          <p>Work we do with your team, each ending in a report you can act on.</p>
        </header>
        <ul class="mk-services">
          <li :for={service <- services()} class={"mk-service mk-service--#{service.id}"}>
            <.field id={"service-#{service.id}-field"} scene="backdrop" class="mk-service__field" />
            <div class="mk-service__words">
              <h3>{service.name}</h3>
              <p>{service.line}</p>
              <.link navigate={service.href} class="mk-service__link">
                See details <Regent.Icons.icon name="arrow-right" />
              </.link>
            </div>
          </li>
        </ul>
      </section>

      <section id="agents" class="mk-section" aria-labelledby="agents-title">
        <header class="mk-section__head">
          <h2 id="agents-title">Agents</h2>
          <p>Your agent can use Techtree from any page of this site, or from the command line.</p>
        </header>
        <div class="mk-split">
          <div id="agents-site" class="mk-panel">
            <h3>Browser</h3>
            <p>An agent built into your browser can use these tools on any Techtree page.</p>
            <ul class="mk-tools">
              <li :for={title <- @site_tools}>{title}</li>
            </ul>
            <.link navigate={~p"/docs/browser-agents"} class="text-link">
              Browser agents <span aria-hidden="true">→</span>
            </.link>
          </div>
          <div id="agents-cli" class="mk-panel">
            <h3>Command line</h3>
            <p>Install Techtree, then point it at a Skill on your own computer.</p>
            <%= cond do %>
              <% @catalog == :unreadable -> %>
                <p class="release-state" role="status">
                  The command can't be shown right now. Try again in a minute.
                </p>
              <% is_nil(@release) or not @release.installable? -> %>
                <p class="release-state">There's no version of Techtree to install yet.</p>
              <% true -> %>
                <.command_block
                  id="copy-home-cli"
                  lines={[
                    {:command, @release.install_argv},
                    {:command,
                     ["regents", "techtree", "forge", "inspect-skill", "path/to/your-skill"]}
                  ]}
                  label="Install"
                />
            <% end %>
            <p class="mk-links">
              <.link navigate={~p"/start"} class="text-link">
                Every way to start <span aria-hidden="true">→</span>
              </.link>
              <.link navigate={~p"/docs/api"} class="text-link">
                Public API <span aria-hidden="true">→</span>
              </.link>
            </p>
          </div>
        </div>
      </section>

      <div class="mk-section mk-split mk-split--even">
        <section id="status" aria-labelledby="status-title">
          <h2 id="status-title">Status</h2>
          <p>
            Techtree is a working technical preview built from three independent parts:
            <a href="https://github.com/PrimeIntellect-ai/verifiers">Prime Intellect’s Verifiers</a>
            scores each Climb’s tasks,
            <a href="https://github.com/NousResearch/hermes-agent">Nous Research’s Hermes</a>
            runs the agent, and Techtree runs the comparison and keeps the evidence.
          </p>
          <p :if={@release} class="small quiet">
            Current release: {ReleaseInfo.label(@release)} ·
            <.link navigate={~p"/changelog"}>Changelog</.link>
          </p>
          <ul class="mk-status">
            <li :for={capability <- @capabilities}>
              <span>{capability.name}</span>
              <.capability_status capability={capability.id} />
            </li>
          </ul>
        </section>
        <section id="privacy" aria-labelledby="privacy-title">
          <h2 id="privacy-title">Privacy</h2>
          <p>
            Techtree doesn’t watch your runs. Your work stays local unless you choose to publish
            the finished Result bundle. Model calls go to the model provider you run with, under
            that provider’s policies.
          </p>
          <p>
            <a href={~p"/verify"}>What verification establishes <span aria-hidden="true">→</span></a>
          </p>
        </section>
      </div>

      <section :if={@news != []} id="news" class="mk-section" aria-labelledby="news-title">
        <header class="mk-section__head mk-section__head--row">
          <h2 id="news-title">News</h2>
          <.link navigate={~p"/changelog"} class="text-link">
            Changelog <span aria-hidden="true">→</span>
          </.link>
        </header>
        <ul class="mk-news">
          <li :for={item <- @news}>
            <a href={item.href} class="mk-news__card">
              <span class="mk-news__meta">
                <span>{item.kind}</span>
                <time datetime={Date.to_iso8601(item.date)}>
                  {Calendar.strftime(item.date, "%-d %b %Y")}
                </time>
              </span>
              <h3 class="mk-news__title">{item.title}</h3>
              <span :if={item.line} class="mk-news__line">{item.line}</span>
              <span class="mk-news__more">Read <Regent.Icons.icon name="arrow-right" /></span>
            </a>
          </li>
        </ul>
      </section>

      <section id="begin" class="mk-closing mk-dark" aria-labelledby="begin-title">
        <.field id="begin-field" scene="glow" class="mk-closing__field" />
        <div class="mk-closing__copy">
          <h2 id="begin-title">Get started</h2>
          <p class="mk-closing__line">Improve a Skill. Prove it worked.</p>
          <div class="mk-hero__actions">
            <.link navigate={~p"/start"} class="rg-button rg-button--primary">Start</.link>
            <BookCall.book_call variant={:secondary} />
          </div>
        </div>
      </section>
    </Layouts.page>
    """
  end

  @doc """
  The home page's one short line for an agent. The agent guide it points at
  carries the steps and the stops; /start keeps the longer instruction.
  """
  def agent_line do
    "Read #{url(~p"/agents.md")} and help me test one of my Skills with Techtree. " <>
      "Ask me before any paid model call or before publishing anything."
  end

  # The Products row. Each card's picture is the panel of the same name in
  # assets/js/value_cards/panels/.
  defp products do
    [
      %{
        id: "compare",
        name: "Evaluate & Climb",
        headline: "See what a Skill changes.",
        line: "Check your Skill, then compare your agent with and without it.",
        tint: "#3fbf7f",
        action: "Start",
        navigate: ~p"/start"
      },
      %{
        id: "wallet",
        name: "Wallet Bench",
        headline: "Agents and wallets, tested.",
        line: "See which coding agents can set up which wallet tools safely.",
        tint: "#6fdba0",
        action: "See scores",
        navigate: ~p"/wallet-bench"
      },
      %{
        id: "train",
        name: "Train",
        headline: "One change, measured.",
        line: "See NVIDIA Nemotron models scored before and after one change.",
        tint: "#38b2e0",
        action: "See comparisons",
        navigate: ~p"/train"
      },
      %{
        id: "check",
        name: "Offline check",
        headline: "Results you can verify.",
        line: "Download a signed Result and check it on your own computer.",
        tint: "#b5d94a",
        action: "Check Result",
        navigate: ~p"/verify"
      },
      %{
        id: "repo",
        name: "Repo2RLEnv",
        headline: "Practice from real code.",
        line: "Coming soon: past fixes in your repository become practice tasks for agents.",
        tint: "#2fc4c4",
        action: "Learn more",
        navigate: ~p"/repo2rlenv"
      },
      %{
        id: "watch",
        name: "Watchdog",
        headline: "Keep watch on your sites.",
        line:
          "We test sites you prove you own for security weaknesses, then retest after you fix.",
        tint: "#f0a531",
        action: "See details",
        navigate: ~p"/services/watchdog"
      }
    ]
  end

  # The three services, each a tall card in its own colours.
  defp services do
    [
      %{
        id: "verify",
        name: "Verify",
        line: "Prove your important workflows work.",
        href: ~p"/services/verify"
      },
      %{
        id: "cyber-assist",
        name: "Cyber Assist",
        line: "Find and fix the security weaknesses that matter.",
        href: ~p"/services/cyber-assist"
      },
      %{
        id: "watchdog",
        name: "Watchdog",
        line: "Keep watch on the sites you own.",
        href: ~p"/services/watchdog"
      }
    ]
  end

  # The site's figures, each only once there is one to show.
  defp figures(climbs) do
    for {value, label, href} <- [
          {Results.count(), "Published Results", ~p"/results"},
          {length(climbs), "Published Climbs", "#climbs"},
          {WalletBenchScores.figures().agents, "Agents tested", ~p"/wallet-bench"},
          {length(Comparisons.list()), "Train comparisons", ~p"/train"}
        ],
        value > 0,
        do: %{value: value, label: label, href: href}
  end

  defp results(entries) do
    runs = Results.runs(entries)

    for entry <- entries do
      %{
        entry: entry,
        runs: Map.fetch!(runs, entry.bundle_digest),
        verdict: Verdict.of(entry.assessment)
      }
    end
  end

  # The newest Result's tasks as squares, better, same or worse, scaled down
  # past @most_cells; with none yet, a plain row of squares.
  defp cells(%{entry: %{wins: wins, ties: ties, losses: losses}})
       when wins + ties + losses > 0 do
    total = wins + ties + losses
    scale = min(1, @most_cells / total)

    Enum.flat_map(
      [{"better", wins}, {"same", ties}, {"worse", losses}],
      fn {kind, count} -> List.duplicate(kind, round(count * scale)) end
    )
  end

  defp cells(_newest), do: List.duplicate("plain", 12)

  # Where the Verdict card's needle points, in degrees from straight up.
  defp angle(:improved), do: 60
  defp angle(:regressed), do: -60
  defp angle(_verdict), do: 0

  defp mark, do: @mark

  defp names(ids, fetch!), do: ids |> Enum.map(&fetch!.(&1).name) |> Enum.sort()

  defp climb_with_slug(climbs, slug), do: Enum.find(climbs, &(&1.projection["slug"] == slug))

  attr :by, :string, required: true, doc: "whose projects these are, as the Stack names them"

  # The logo of a maker whose projects Techtree is built on: its own file, from
  # its own site, unchanged (`priv/static/images/built-on/`). Each sits on the
  # same light plate in both themes. These are the only logos on the site.
  defp maker_logo(assigns) do
    assigns = assign(assigns, :logo, logo(assigns.by))

    ~H"""
    <img
      class={["mk-maker__logo", "mk-maker__logo--#{@logo.id}"]}
      src={@logo.src}
      alt={@logo.name}
      width={@logo.width}
      height={@logo.height}
    />
    """
  end

  defp logo("Prime Intellect’s"),
    do: %{
      id: "prime-intellect",
      name: "Prime Intellect",
      src: ~p"/images/built-on/prime-intellect.svg",
      width: 899,
      height: 161
    }

  defp logo("NVIDIA’s"),
    do: %{
      id: "nvidia",
      name: "NVIDIA",
      src: ~p"/images/built-on/nvidia.svg",
      width: 2560,
      height: 1440
    }

  defp logo("Nous Research’s"),
    do: %{
      id: "nous-research",
      name: "Nous Research",
      src: ~p"/images/built-on/nous-research.svg",
      width: 200,
      height: 280
    }

  attr :id, :string, required: true
  attr :scene, :string, values: ~w(glow screen mark backdrop), required: true
  attr :shape, :integer, default: nil
  attr :class, :string, default: nil
  slot :inner_block

  # A moving picture (`assets/js/marketing/field_hook.ts`) over the still the
  # stylesheet draws, which stays for less motion and where WebGPU is missing.
  defp field(assigns) do
    ~H"""
    <div
      id={@id}
      class={["mk-field", "mk-field--#{@scene}", @class]}
      phx-hook="MarketingField"
      phx-mounted={JS.ignore_attributes(["data-field-ready", "data-field-shape"])}
      data-field={@scene}
      data-field-shape={@shape}
      aria-hidden="true"
    >
      <div class="mk-field__still">{render_slot(@inner_block)}</div>
      <canvas id={"#{@id}-canvas"} class="mk-field__canvas" phx-update="ignore" data-field-canvas></canvas>
    </div>
    """
  end

  attr :results, :list, required: true

  # The newest published Results, the first in the middle. The carousel hook
  # owns each card's place from here (`assets/js/marketing/carousel.ts`).
  defp carousel(assigns) do
    assigns = assign(assigns, :count, length(assigns.results))

    ~H"""
    <section
      id="hero-results"
      class="mk-carousel"
      aria-label="Published Results"
      aria-roledescription="carousel"
      phx-hook="MarketingCarousel"
      phx-update="ignore"
      data-entrance-part
    >
      <div class="mk-carousel__stage" data-carousel-stage aria-live="polite">
        <.result_card
          :for={{result, index} <- Enum.with_index(@results)}
          result={result}
          index={index}
          count={@count}
        />
      </div>
      <div class="mk-carousel__controls">
        <div :if={@count > 1} class="mk-carousel__dots">
          <button
            :for={index <- 0..(@count - 1)}
            type="button"
            class="mk-carousel__dot"
            data-carousel-dot
            aria-label={"Result #{index + 1} of #{@count}"}
            aria-current={to_string(index == 0)}
          >
            <span class="mk-carousel__track"><span class="mk-carousel__fill" data-fill></span></span>
          </button>
        </div>
        <button :if={@count > 1} type="button" class="mk-carousel__pause" data-carousel-pause>
          <Regent.Icons.icon name="pause" class="mk-carousel__paused" />
          <Regent.Icons.icon name="play" class="mk-carousel__playing" />
          <span data-label>Pause</span>
        </button>
        <.link navigate={~p"/results"} class="text-link">
          See every Result <span aria-hidden="true">→</span>
        </.link>
      </div>
    </section>
    """
  end

  attr :result, :map, required: true
  attr :index, :integer, required: true
  attr :count, :integer, required: true

  defp result_card(%{result: %{entry: entry}} = assigns) do
    assigns =
      assign(assigns,
        entry: entry,
        slot: place(assigns.index, assigns.count),
        rows: [
          {"Better", "better", entry.wins},
          {"Same", "same", entry.ties},
          {"Worse", "worse", entry.losses}
        ],
        total: entry.wins + entry.ties + entry.losses
      )

    ~H"""
    <article
      id={@index == 0 && "hero-newest-result"}
      class="mk-result"
      data-carousel-card
      data-slot={@slot}
      aria-roledescription="slide"
      aria-label={"#{@index + 1} of #{@count}"}
      aria-hidden={@slot != "centre" && "true"}
      inert={@slot != "centre"}
    >
      <p class="mk-result__top">
        <span>{if @index == 0, do: "Newest Result", else: "Result"}</span>
        <strong class={["verdict", "verdict--#{@result.verdict}"]}>
          {ResultAssessment.label(@result.verdict)}
        </strong>
      </p>
      <p class="mk-result__title">
        <.link navigate={"/results/" <> @entry.bundle_digest} class="mk-result__link">
          {ResultNames.skill(@entry)} vs baseline
        </.link>
      </p>
      <p class="mk-result__where">{ResultNames.coordinates(@entry)}</p>
      <dl class="mk-result__rows">
        <div :for={{label, kind, value} <- @rows} class="mk-result__row" data-tick>
          <dt>{label}</dt>
          <dd class="mk-result__bar" aria-hidden="true">
            <svg viewBox="0 0 100 6" preserveAspectRatio="none" aria-hidden="true">
              <rect class="mk-result__track" width="100" height="6" />
              <rect
                class={"mk-result__fill mk-result__fill--#{kind}"}
                data-bar
                width={share(value, @total)}
                height="6"
              />
            </svg>
          </dd>
          <dd class="mk-result__figure" data-figure>{value}</dd>
        </div>
      </dl>
      <p class="mk-result__foot">
        <span>{ResultAssessment.runs_words(@result.runs)}</span>
        <span class="mk-result__more">
          See the evidence <Regent.Icons.icon name="arrow-right" />
        </span>
      </p>
    </article>
    """
  end

  # Where the card at `index` starts: the first in the middle, the second next,
  # the last before it (`slotOf` in carousel.ts, with the first card current).
  defp place(0, _count), do: "centre"
  defp place(1, _count), do: "next"
  defp place(index, count) when index == count - 1 and count > 2, do: "prev"
  defp place(_index, _count), do: "away"

  defp share(_value, 0), do: 0
  defp share(value, total), do: round(value / total * 100)

  attr :id, :string, required: true
  attr :name, :string, required: true
  attr :line, :string, required: true
  attr :flip, :boolean, default: false, doc: "put the picture before the items"

  slot :item, required: true do
    attr :title, :string, required: true
    attr :icon, :string, required: true
    attr :shape, :integer, required: true, doc: "the dot picture's shape (SHAPES in scenes.ts)"
    attr :capability, :atom
    attr :open, :boolean
    attr :id, :string
  end

  # One group of products: its items, one open at a time, beside a dot picture
  # that draws the open item's shape (`assets/js/marketing/accordion.ts`).
  defp group(assigns) do
    assigns = assign(assigns, :first, Enum.find(assigns.item, & &1[:open]) || hd(assigns.item))

    ~H"""
    <section
      id={@id}
      class={["mk-section", "mk-group", @flip && "mk-group--flip"]}
      aria-labelledby={"#{@id}-title"}
      phx-hook="MarketingAccordion"
    >
      <div class="mk-group__items">
        <h2 id={"#{@id}-title"}>{@name}</h2>
        <p class="mk-group__line">{@line}</p>
        <details
          :for={{item, index} <- Enum.with_index(@item)}
          id={item[:id] || "#{@id}-#{index}"}
          class="mk-item"
          name={@id}
          open={item[:open]}
          data-shape={item.shape}
          phx-mounted={JS.ignore_attributes(["open"])}
        >
          <summary class="mk-item__summary">
            <Regent.Icons.icon name={item.icon} class="mk-item__icon" />
            <h3 class="mk-item__title">{item.title}</h3>
            <.capability_status :if={item[:capability]} capability={item.capability} />
            <Regent.Icons.icon name="plus" class="mk-item__toggle" />
          </summary>
          <div class="mk-item__body" data-item-body>
            {render_slot(item)}
          </div>
        </details>
      </div>
      <.field id={"#{@id}-picture"} scene="screen" shape={@first.shape} class="mk-group__picture">
        <Regent.Icons.icon
          :for={item <- @item}
          name={item.icon}
          class="mk-group__glyph"
          data-glyph={item.shape}
        />
      </.field>
    </section>
    """
  end
end
