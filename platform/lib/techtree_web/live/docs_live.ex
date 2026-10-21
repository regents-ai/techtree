defmodule TechtreeWeb.DocsLive do
  @moduledoc """
  The Docs: `/docs` lists the guides (`TechtreeWeb.DocsGuides`) and each guide
  has its own page at `/docs/<slug>`.

  Commands containing release coordinates are rendered from the active release
  rather than copied into these pages.
  """

  use TechtreeWeb, :live_view

  import TechtreeWeb.PageCopy, only: [page_copy: 1]

  alias Techtree.Catalog.Query
  alias TechtreeWeb.CampaignFacts
  alias TechtreeWeb.DocsGuides
  alias TechtreeWeb.ModelAccess
  alias TechtreeWeb.Outage
  alias TechtreeWeb.PublicDocuments
  alias TechtreeWeb.ReleaseInfo
  alias TechtreeWeb.StartLive

  @impl true
  def mount(_params, _session, socket) do
    {release, install} =
      case Outage.read(&ReleaseInfo.current/0) do
        {:ok, release} -> {release, :read}
        :database_down -> {nil, :unreadable}
      end

    frontier = release && ReleaseInfo.climb(release, "frontier-cs-open-ended-climb")

    {:ok,
     assign(socket,
       release: release,
       install: install,
       instruction: StartLive.instruction(),
       plugin_commands: plugin_commands(release),
       introductory_routes: release && routes(release.introductory_reference),
       frontier: frontier,
       frontier_routes: routes(frontier)
     )}
  end

  @impl true
  def handle_params(params, _uri, socket) do
    case params do
      %{"slug" => slug} ->
        case DocsGuides.fetch(slug) do
          {:ok, guide} ->
            {:noreply,
             assign(socket,
               page_title: guide.title <> " · Docs",
               guide: guide,
               text: PublicDocuments.guide(slug),
               neighbours: DocsGuides.neighbours(slug)
             )}

          :error ->
            raise TechtreeWeb.NotFoundError, "there is no Docs guide by that name"
        end

      %{} ->
        {:noreply, assign(socket, page_title: "Docs", guide: nil)}
    end
  end

  @impl true
  def render(%{guide: nil} = assigns) do
    ~H"""
    <Layouts.page wide>
      <article class="docs-index" data-markdown-root>
        <header class="docs-hero">
          <div class="docs-hero__top">
            <h1>Docs</h1>
            <.page_copy />
          </div>
          <p class="lede">{DocsGuides.lede()}</p>
        </header>
        <section :for={{group, guides} <- DocsGuides.groups()} class="docs-index__group">
          <h2>{group}</h2>
          <ul class="docs-index__list">
            <li :for={guide <- guides}>
              <.link navigate={~p"/docs/#{guide.slug}"} class="docs-index__link">
                <span>{guide.title}</span>
                <small>{guide.summary}</small>
              </.link>
            </li>
          </ul>
        </section>
      </article>
    </Layouts.page>
    """
  end

  # A guide's body is committed Markdown rendered at compile time (`PublicDocuments.guide/1`).
  # sobelow_skip ["XSS.Raw"]
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <div class="docs-layout">
        <article class="docs-content" data-markdown-root>
          <header class="docs-hero">
            <div class="docs-hero__top">
              <p class="eyebrow">{@guide.group}</p>
              <.page_copy />
            </div>
            <h1>{@text.title}</h1>
            <p class="lede">{raw(lede_html(@text.lede))}</p>
          </header>
          <.guide
            slug={@guide.slug}
            text={@text}
            release={@release}
            install={@install}
            instruction={@instruction}
            plugin_commands={@plugin_commands}
            introductory_routes={@introductory_routes}
            frontier={@frontier}
            frontier_routes={@frontier_routes}
          />
          <nav class="docs-pager" aria-label="Next and previous guides" data-markdown-skip>
            <.link :if={elem(@neighbours, 0)} navigate={~p"/docs/#{elem(@neighbours, 0).slug}"}>
              <small>Previous</small> {elem(@neighbours, 0).title}
            </.link>
            <.link
              :if={elem(@neighbours, 1)}
              navigate={~p"/docs/#{elem(@neighbours, 1).slug}"}
              class="docs-pager__next"
            >
              <small>Next</small> {elem(@neighbours, 1).title}
            </.link>
          </nav>
        </article>

        <aside class="docs-nav" aria-label="All guides" data-markdown-skip>
          <p class="docs-nav__version">
            <.link navigate={~p"/docs"}>All guides</.link>
            <span :if={@release}>· Techtree {ReleaseInfo.label(@release)}</span>
          </p>
          <nav>
            <div :for={{group, guides} <- DocsGuides.groups()} class="docs-nav__group">
              <p>{group}</p>
              <.link
                :for={guide <- guides}
                navigate={~p"/docs/#{guide.slug}"}
                aria-current={guide.slug == @guide.slug && "page"}
              >
                {guide.title}
              </.link>
            </div>
          </nav>
        </aside>
      </div>
    </Layouts.page>
    """
  end

  # The lede is one Markdown paragraph; links in it stay links.
  defp lede_html(lede) do
    {html, _contents} = RegentBlog.markdown(lede)
    html |> String.trim() |> String.trim_leading("<p>") |> String.trim_trailing("</p>")
  end

  attr :html, :string, required: true

  # PublicDocuments.guide/1 renders the committed guide Markdown at compile time; no request HTML enters it.
  # sobelow_skip ["XSS.Raw"]
  defp prose(assigns) do
    ~H"""
    <div class="docs-prose">{raw(@html)}</div>
    """
  end

  defp guide(%{slug: "install"} = assigns) do
    ~H"""
    <section class="doc-section">
      <%= cond do %>
        <% @install == :unreadable -> %>
          <p role="status">
            The install steps can't be shown right now. Try again in a minute.
          </p>
        <% is_nil(@release) or not @release.installable? -> %>
          <p>There's no version of Techtree to install yet.</p>
        <% @release.introductory_reference -> %>
          <.command_block
            id="copy-docs-install"
            lines={[
              {:command, @release.install_argv},
              {:comment, "It should print #{@release.version}:"},
              {:command, ["regents", "--version"]},
              {:command,
               ["regents", "techtree", "doctor", "--climb", @release.introductory_reference]}
            ]}
            label="Install, check, then run Doctor"
          />
          <p class="small quiet">
            Doctor checks what this machine needs without calling a model. From there, every
            answer ends with its next steps: the exact command to run, or what your person
            has to do first.
          </p>
        <% true -> %>
          <p>This release does not name an introductory Climb.</p>
      <% end %>
    </section>
    """
  end

  defp guide(%{slug: "test-a-skill"} = assigns) do
    ~H"""
    <section class="doc-section">
      <h2>1. Make the tasks</h2>
      <.command_block
        id="copy-docs-skill-tasks"
        lines={[
          {:command, ["regents", "techtree", "forge", "inspect-skill", "path/to/your-skill"]},
          {:command,
           [
             "regents",
             "techtree",
             "forge",
             "plan",
             "SOURCE_ID",
             "--provider",
             "PROVIDER",
             "--model",
             "MODEL"
           ]},
          {:comment, "Review, correct, build and accept, one printed step at a time."}
        ]}
        label="Make tasks from a Skill"
      />
      <p>
        Accepting the tasks that qualified gives you a collection. Some of its tasks are
        held out from anyone improving the Skill.
      </p>
      <h2>2. Run them both ways, then compare</h2>
      <.command_block
        id="copy-docs-skill-compare"
        lines={[
          {:command,
           [
             "regents",
             "techtree",
             "forge",
             "run",
             "--arm",
             "baseline",
             "--collection",
             "COLLECTION_ID",
             "--provider",
             "PROVIDER",
             "--model",
             "MODEL"
           ]},
          {:command,
           [
             "regents",
             "techtree",
             "forge",
             "run",
             "--arm",
             "candidate",
             "--collection",
             "COLLECTION_ID",
             "--provider",
             "PROVIDER",
             "--model",
             "MODEL",
             "--skill",
             "path/to/your-skill"
           ]},
          {:command,
           ["regents", "techtree", "forge", "compare", "BASELINE_RUN_ID", "CANDIDATE_RUN_ID"]}
        ]}
        label="Compare without and with the Skill"
      />
      <p>
        Both runs use the same provider and model. The comparison calls no model: it pairs
        every task across the two runs and says whether the Skill improved, regressed, was
        mixed or made no difference, overall and on the held-out tasks alone. It writes a
        report you can open in a browser. The <.link navigate={~p"/examples/tdd"}>tdd example</.link>
        shows a finished one.
      </p>
      <h2 id="two-versions">Compare two versions of a Skill</h2>
      <p>
        To decide whether a change is worth keeping, give the baseline run the earlier
        version instead of no Skill. Keep the earlier version in its own folder, then run the
        candidate with the new version and compare the two runs as above.
      </p>
      <.command_block
        id="copy-docs-two-versions"
        argv={[
          "regents",
          "techtree",
          "forge",
          "run",
          "--arm",
          "baseline",
          "--collection",
          "COLLECTION_ID",
          "--provider",
          "PROVIDER",
          "--model",
          "MODEL",
          "--skill",
          "path/to/earlier-skill"
        ]}
        label="Baseline with the earlier version"
      />
      <h2>3. Revise once, if you want to</h2>
      <p>
        <code>regents techtree uplift context COMPARISON_ID</code>
        gives what a revision may learn from, never the held-out tasks. Write the revised
        Skill into a new folder, then run
        <code>
          regents techtree uplift prepare --from-run COMPARISON_ID --candidate-skill path/to/revised-skill
        </code>
        and the <code>regents techtree uplift start</code>
        command it prints. The revision is judged on the held-out tasks alone.
      </p>
      <h2>Fix a task, or check where things stand</h2>
      <p>
        If a built task is wrong, fix a copy of it by hand and record that with <code>regents techtree forge correct-task CONSTRUCTION_ID TASK_NAME DIR</code>.
        <code>regents techtree forge status ID</code>
        shows any build, plan, run or comparison.
        <code>regents techtree forge export COLLECTION_ID --to FOLDER</code>
        writes a copy of the tasks for someone else to read.
      </p>
    </section>
    """
  end

  defp guide(%{slug: "hello-world"} = assigns) do
    ~H"""
    <section class="doc-section">
      <.command_block
        :if={@release && @release.introductory_reference}
        id="copy-docs-prepare"
        lines={
          [{:command, ["regents", "techtree", "skill", "starter"]}] ++
            ModelAccess.prepare_lines(@introductory_routes, [
              "regents",
              "techtree",
              "climb",
              "prepare",
              @release.introductory_reference,
              "--skill",
              "path/to/skill"
            ])
        }
        label="Prepare the Hello World Climb"
      />
      <p>
        Approve and run only the exact <code>regents techtree climb start</code>
        command printed by preparation. Closing the terminal does not stop a started run.
      </p>
      <.prose html={@text.body_html} />
    </section>
    """
  end

  defp guide(%{slug: "frontier-cs"} = assigns) do
    ~H"""
    <section class="doc-section">
      <p>Start from its starter Skill, or from your own.</p>
      <.command_block
        :if={@frontier_routes}
        id="copy-docs-frontier"
        lines={
          [{:command, ["regents", "techtree", "skill", "starter", "--climb", @frontier]}] ++
            ModelAccess.prepare_lines(@frontier_routes, [
              "regents",
              "techtree",
              "climb",
              "prepare",
              @frontier,
              "--skill",
              "path/to/skill"
            ])
        }
        label="Prepare the Frontier-CS Open-Ended Climb"
      />
    </section>
    """
  end

  defp guide(%{slug: "hermes"} = assigns) do
    ~H"""
    <section class="doc-section">
      <.prompt_block id="copy-docs-hermes" label="Give this to Hermes" text={@instruction} />
      <p>
        Hermes may prepare commands and explain output. Techtree still stops before every
        model call and waits for your own yes.
      </p>
      <p :if={@plugin_commands}>
        The Techtree plugin for Hermes adds commands for the Hello World Climb and for
        publishing its Results:
      </p>
      <.command_block
        :if={@plugin_commands}
        id="copy-docs-hermes-plugin"
        lines={@plugin_commands}
        label="Hermes plugin"
      />
    </section>
    """
  end

  defp guide(%{slug: "verify"} = assigns) do
    ~H"""
    <section class="doc-section">
      <.command_block
        id="copy-docs-verify"
        argv={["regents", "techtree", "proof", "verify", "path/to/result-bundle"]}
        label="Check on this computer"
      />
      <.prose html={@text.body_html} />
      <p><.link navigate={~p"/verify"}>Read exactly what a check establishes.</.link></p>
    </section>
    """
  end

  defp guide(%{slug: "publish"} = assigns) do
    ~H"""
    <section class="doc-section">
      <.command_block
        id="copy-docs-publish"
        argv={["regents", "techtree", "publish", "RUN_ID"]}
        label="Publish one finished run"
      />
      <.command_block
        id="copy-docs-withdraw"
        argv={["regents", "techtree", "withdraw", "BUNDLE_DIGEST"]}
        label="Withdraw a published Result"
      />
      <.prose html={@text.body_html} />
    </section>
    """
  end

  defp guide(assigns) do
    ~H"""
    <section class="doc-section"><.prose html={@text.body_html} /></section>
    """
  end

  defp plugin_commands(%{
         installable?: true,
         plugin_install_argv: [_ | _] = install_argv,
         plugin_doctor_argv: [_ | _] = doctor_argv
       }) do
    [
      {:command, install_argv},
      {:command, doctor_argv},
      {:comment, "In a fresh Hermes session, enter:"},
      {:command, ["/techtree", "setup"]}
    ]
  end

  defp plugin_commands(_release), do: nil

  # The routes a Climb offers, each with its own prepare command.
  defp routes(nil), do: nil

  defp routes(reference),
    do:
      reference
      |> Query.get_climb_by_reference!()
      |> CampaignFacts.trial!()
      |> Map.fetch!(:routes)
end
