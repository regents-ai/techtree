defmodule TechtreeWeb.Plugs.PageMarkdown do
  @moduledoc """
  The Markdown answer of the public pages built from the database or from
  release files: Start, Results, each Result, each Climb, the Wallet Bench, the
  two offers under `/services` and the tdd example. The database-free pages are answered before the router
  (`TechtreeWeb.PublicDocuments`); these wait for the router, so an HTML
  request reads nothing here and a Markdown one reads only what its page reads,
  through the same queries.

  It runs after `accepts`. A request that chose Markdown gets the page's
  Markdown, with the closing line every Markdown page carries (the Wallet Bench
  answers exactly as `/wallet-bench.md` does); one whose page has no Markdown is
  refused with 406, as before. Every other request goes on to the page
  untouched.
  """

  @behaviour Plug

  import Plug.Conn

  alias Techtree.Catalog.Query, as: Catalog
  alias Techtree.Network.Query
  alias TechtreeWeb.CampaignFacts
  alias TechtreeWeb.ClimbCopy
  alias TechtreeWeb.ModelAccess
  alias TechtreeWeb.PublicDocuments
  alias TechtreeWeb.ReleaseInfo
  alias TechtreeWeb.TddShowcase

  @pages %{
    TechtreeWeb.StartLive => :start,
    TechtreeWeb.RunsLive.Index => :results,
    TechtreeWeb.RunsLive.Show => :result,
    TechtreeWeb.ClimbsLive.Show => :climb,
    TechtreeWeb.WalletBenchLive.Index => :wallet_bench,
    TechtreeWeb.ServiceLive => :offer,
    TechtreeWeb.TddShowcaseLive => :tdd
  }

  @doc """
  Whether the page this request reached answers Markdown, before or in the
  router, for the root layout's alternate link.
  """
  @spec markdown?(Plug.Conn.t()) :: boolean()
  def markdown?(conn), do: PublicDocuments.document?(conn.request_path) or page(conn) != nil

  @impl Plug
  def init(opts), do: opts

  @impl Plug
  def call(conn, _opts) do
    case {Phoenix.Controller.get_format(conn), page(conn)} do
      {"md", nil} ->
        raise Phoenix.NotAcceptableError,
          message: "this page has no Markdown",
          accepts: ["html"]

      {"md", :wallet_bench} ->
        conn |> TechtreeWeb.WalletBenchController.markdown(%{}) |> halt()

      {"md", page} ->
        conn
        |> Phoenix.Controller.put_secure_browser_headers()
        |> put_resp_content_type("text/markdown", "utf-8")
        |> send_resp(200, markdown(page, conn) <> PublicDocuments.trailer())
        |> halt()

      _html ->
        conn
    end
  end

  defp page(conn) do
    case conn.private[:phoenix_live_view] do
      {view, _opts, _session} -> Map.get(@pages, view)
      _controller -> nil
    end
  end

  defp markdown(:start, _conn), do: start(ReleaseInfo.current())

  defp markdown(:results, conn) do
    case Query.read_page_options(conn.query_params) do
      {:ok, options} -> results(Query.page(options))
      {:error, reason} -> raise Plug.BadRequestError, message: reason
    end
  end

  defp markdown(:result, %{path_params: %{"bundle_digest" => digest}}) do
    case Query.get_entry(digest) do
      {:ok, entry} -> result(entry)
      :error -> raise TechtreeWeb.NotFoundError, "no run is published under that fingerprint"
    end
  end

  defp markdown(:climb, %{path_params: %{"slug" => slug}}) do
    case Catalog.get_climb_by_slug(slug) do
      {:ok, climb} -> climb(climb)
      {:error, _error} -> raise TechtreeWeb.NotFoundError, "no Climb is published under that name"
    end
  end

  defp markdown(:tdd, _conn), do: tdd(TddShowcase.load!(TddShowcase.folder()))

  defp markdown(:offer, %{private: %{phoenix_live_view: {_view, opts, _session}}}) do
    offer = Keyword.fetch!(opts, :action)
    figures = TechtreeWeb.ServiceLive.figures()

    offer
    |> PublicDocuments.offer()
    |> String.replace("{{bench}}", TechtreeWeb.ServiceLive.bench_markdown(figures))
  end

  defp start(%{installable?: true, introductory_reference: reference} = release) do
    """
    # Choose where to start

    To see what a Skill changes, Techtree makes tasks from it and your agent works them twice: once without the Skill, or with its earlier version, and once with it. Only the Skill changes, so the difference is the Skill's.

    ## Test my Skill

    Give this to a coding agent that can use your terminal, or to Hermes:

    > #{TechtreeWeb.StartLive.instruction()}

    Or set it up yourself:

    ```sh
    #{Enum.join(release.install_argv, " ")}
    regents techtree forge inspect-skill path/to/your-skill
    regents techtree forge plan --help
    ```

    Nothing is uploaded to Techtree. Making the tasks and running them send your Skill's files and the tasks to the model provider you chose, only after you approve the review that says so.

    ## Take a quick look

    #{quick_look(reference)}
    The [agent guide](/agents.md) has every step.
    """
  end

  defp start(_release) do
    """
    # Choose where to start

    There's no version of Techtree to install yet. The [Docs](/docs) explain how a test works in the meantime.
    """
  end

  defp quick_look(reference) do
    trial = reference |> Catalog.get_climb_by_reference!() |> CampaignFacts.trial!()

    commands =
      trial.routes
      |> ModelAccess.prepare_lines([
        "regents",
        "techtree",
        "climb",
        "prepare",
        reference,
        "--skill",
        "path/to/skill"
      ])
      |> Enum.map_join("\n", fn
        {:comment, text} -> "# " <> text
        {:command, argv} -> Enum.join(argv, " ")
      end)

    """
    The Hello World Climb (`#{reference}`) is a small, fixed challenge that ships with the release, run without a Skill and with a starter Skill. Its toy tasks say nothing about your own Skill. The model is `#{trial.model_id}`, run on #{ModelAccess.destinations(trial.routes)}.

    ```sh
    regents techtree setup
    regents techtree doctor --climb #{reference}
    regents techtree skill starter
    #{commands}
    ```
    """
  end

  defp results(%{entries: entries, next_before_sequence: next}) do
    rows =
      case entries do
        [] -> "No Results are published here yet."
        entries -> Enum.map_join(entries, "\n", &result_row/1)
      end

    more =
      if next,
        do: "\n\n[Older Results](/results?before_sequence=#{next})",
        else: ""

    """
    # Published Results

    Every Climb run somebody has published, newest first. This site checked that each receipt is consistent and signed by the key it names; it did not watch the run or repeat it. Each Result's bundle can be checked offline with `regents techtree proof verify`. The same log as JSON: [/api/v1/publications](/api/v1/publications).

    #{rows}#{more}
    """
  end

  defp result_row(entry) do
    withdrawn = if Query.withdrawn?(entry), do: " Withdrawn.", else: ""

    "- [#{entry.campaign_name}](/results/#{entry.bundle_digest}): " <>
      "#{score(entry.baseline_mean)} without the Skill and #{score(entry.candidate_mean)} with it, " <>
      "#{entry.subject_model} on #{entry.subject_harness}. " <>
      "Published #{Calendar.strftime(entry.accepted_at, "%d %b %Y")}.#{withdrawn}"
  end

  defp result(entry) do
    withdrawn =
      if Query.withdrawn?(entry),
        do:
          "\nThis Result was withdrawn on #{date(entry.withdrawn_at)}; its bundle is no longer offered.\n",
        else: ""

    skill =
      if entry.skill_name,
        do: "- Skill: #{entry.skill_name} (the publisher gave this name; nothing checked it)\n",
        else: ""

    """
    # #{entry.campaign_name} · Published Result
    #{withdrawn}
    - Mean score: #{score(entry.baseline_mean)} without the Skill, #{score(entry.candidate_mean)} with it
    - Tasks: #{entry.wins} better, #{entry.losses} worse, #{entry.ties} the same, of #{entry.task_count}
    - Agent: #{entry.subject_harness} #{entry.subject_harness_version}, #{entry.subject_model} on #{entry.subject_provider}
    #{skill}- Checks this site ran on the receipt: #{entry.verification_checks_passed} of #{entry.verification_checks_run} passed
    - Published: #{date(entry.accepted_at)}
    - Runs behind it: #{Query.runs_behind(entry)}

    This site checked that the receipt is consistent and signed by the key it names. It did not watch the run and did not repeat it. Check the bundle yourself, offline:

    ```sh
    regents techtree proof verify path/to/result-bundle
    ```

    The bundle: [/api/v1/publications/#{entry.bundle_digest}/bundle](/api/v1/publications/#{entry.bundle_digest}/bundle). The record as JSON: [/api/v1/publications/#{entry.bundle_digest}](/api/v1/publications/#{entry.bundle_digest}).
    """
  end

  defp climb(climb) do
    copy = ClimbCopy.for_reference(climb.reference)
    trial = CampaignFacts.trial!(climb)

    scope = if copy, do: "\n#{copy.scope}\n", else: ""
    question = if copy, do: "- Question: #{copy.question}\n", else: ""

    """
    # #{climb.title}
    #{scope}
    #{question}- Tasks: #{climb.projection["task_count"]}, fixed before either Run
    - Model: `#{trial.model_id}`, run on #{ModelAccess.destinations(trial.routes)}
    - Reference: `#{climb.reference}`

    Each Run works the same tasks without the Skill and with it. Run `regents techtree climb show #{climb.reference}` for this Climb's next steps, after installing the release [Start](/start) names. Published Results from it are at [Results](/results).
    """
  end

  defp tdd(showcase) do
    claims =
      Enum.map_join(showcase.claims, "\n", fn claim ->
        "- #{claim.statement} (#{length(claim.tasks)} tasks)"
      end)

    """
    # #{showcase.skill.name} vs No Skill

    A local comparison of the #{showcase.skill.name} Skill against no Skill, reported by the person who ran it on #{date(showcase.created_at)}. Nothing here is signed: it is one comparison on one computer.

    - Held-out tasks: #{verdict(showcase.held_out.verdict)}, #{part(showcase.held_out)}
    - Tasks an improving agent may study: #{verdict(showcase.study.verdict)}, #{part(showcase.study)}
    - Model: `#{showcase.model.model_id}` on #{showcase.model.provider}
    - Skill licence: #{showcase.skill.licence.name}. #{showcase.skill.licence.copyright}

    ## What the Skill claims

    #{claims}

    The task files: [#{TddShowcase.export_url()}](#{TddShowcase.export_url()}).
    """
  end

  defp part(part),
    do:
      "#{part.wins} better, #{part.losses} worse, #{part.ties} the same, #{part.unresolved} unresolved"

  defp verdict(:improved), do: "improved"
  defp verdict(:regressed), do: "regressed"
  defp verdict(:mixed), do: "mixed"
  defp verdict(:no_difference), do: "no difference"
  defp verdict(:inconclusive), do: "inconclusive"

  defp score(nil), do: "no score"
  defp score(mean), do: :erlang.float_to_binary(mean / 1, decimals: 3)

  defp date(datetime), do: Calendar.strftime(datetime, "%d %b %Y")
end
