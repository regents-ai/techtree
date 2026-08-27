defmodule TechtreeWeb.ReleaseCopyTest do
  @moduledoc """
  The claims this site is not allowed to make.

  Six sentences are easy to write and wrong to publish: that a trial happens
  entirely on the reader's own machine, that entering needs no account at all,
  that anyone but the participant witnessed the run, that the reader picked the
  model the agent under test answers with, that the guided revision will make
  the Skill better, and that the introductory Skill scores a particular number.
  Each of them is close enough to the truth that it survives a careful edit,
  which is why it is checked here instead.

  Two things are the other way round: they have to be there. Hermes reads the
  plugin's source before installing it and reports what it found, and a page
  that tells a reader what that report will say also has to tell them that
  switching the reporting off is not one of the answers. And a page that says
  what this release is has to say the whole of it — a proof of concept for a
  stack of three independent parts, two of them somebody else's work, pinned to
  exact versions the release is no more reproducible than.

  Every source of published words is read here: each page as a reader sees it,
  with a release being served and with none, the installation contract this
  site publishes, and the text of the modules the pages are written in — so a
  sentence that only appears for a Climb in some other state is caught before
  a reader ever reaches it.
  """

  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture

  @pages [
    "/",
    "/docs",
    "/campaigns",
    "/campaigns/hello-world-climb",
    "/proofs",
    "/start",
    "/climbs",
    "/climbs/hello-world-climb",
    "/proofs/local",
    "/protocol"
  ]

  @pages_without_catalog [
    "/",
    "/docs",
    "/campaigns",
    "/proofs",
    "/start",
    "/climbs",
    "/proofs/local",
    "/protocol"
  ]

  # The addresses that carry one of the two installation paths. Which page
  # offers which is a design decision and has moved once already; that a page
  # offering one carries its exact words has not moved and is not allowed to.
  @install_paths ["/", "/start", "/?install=me", "/start?install=me", "/docs"]

  # A claim that the machine keeps everything, which the remote model calls a
  # trial makes contradict unless the same passage says so.
  @unqualified_privacy [
    "nothing leaves the laptop",
    "nothing leaves your laptop",
    "nothing leaves the machine",
    "nothing is sent anywhere",
    "fully offline evaluation"
  ]

  # Near a privacy claim the same passage has to name where the model calls go.
  @privacy_qualification_window 400
  @privacy_names_the_calls ~r/model (calls?|inference|requests?)/i
  @privacy_names_the_recipient ~r/(model|inference) provider|provider[’']s policies/i

  # "No Techtree account is required" is true. Dropping the word Techtree makes
  # it false: a provider account, a credential, and a network are all needed.
  @unscoped_account ~r/\bno\s+accounts?\s+(is\s+|are\s+)?(required|needed|to hold)\b/i

  # The Campaign pins the model the agent under test answers with. "Your own
  # model" tells a reader they picked it, and blurs that subject with the
  # ordinary model their own agent runs on. Naming the provider is fine — a
  # participant does bring their own provider account and key.
  @blurred_model ~r/\byour own models?\b/i

  # The guided revision is one proposal from a model, tested honestly. Any
  # sentence that promises it lands is a promise about somebody else's model.
  @promised_revision [
    ~r/will fix (the|your) skill/i,
    ~r/learns? from (its|their|your) mistakes/i,
    ~r/(will|to) close the gap/i
  ]

  @dishonest_attestation [
    ~r/techtree\s+verified/i,
    ~r/verified\s+by\s+techtree/i,
    ~r/independently\s+verified/i,
    ~r/independently\s+proven/i,
    ~r/trustless/i,
    ~r/proof\s+of\s+honest\s+compute/i,
    ~r/without\s+trusting\s+us/i
  ]

  # The calibrated public claim is a band, described in words. A number pinned
  # to the task count reads as a promise about the next run.
  @exact_score_claim [
    ~r/\b\d{1,3}\s*(\/|out of)\s*36\b/i,
    ~r/\b\d{1,3}\s*%\s*(of\s+)?(the\s+)?(toy\s+)?tasks\b/i,
    ~r/\bscores?\s+\d{1,3}\b/i
  ]

  # A Climb's terms describe what publication would mean for a result produced
  # under them. This release performs none of it, and the terms read as a
  # threat to a careful reader unless the same passage says so.
  @publication_terms [
    "Would be published as part of entering",
    "Under these terms nothing you submit is treated as private",
    "May be published under these terms"
  ]

  @publishes_nothing [
    "Nothing you produce is published.",
    "stay on your machine, and there is nowhere on this site to send them"
  ]

  @forbidden_name ~r/helloworldbench/i

  # This release publishes nothing and receives nothing, and the pages that
  # describe a finished comparison are exactly the pages tempted to offer the
  # parts of it that do not exist yet: something to download, somebody else's
  # attestation, a place to publish.
  @offered_publication [
    ~r/\bdownload\b[^.]{0,60}\bbundle\b/i,
    ~r/reproduction attestations?/i,
    ~r/\bpublish (your|the) (proof|result|bundle)\b/i,
    ~r/\bupload (your|the|a) (proof|result bundle)\b/i
  ]

  # A stand-in coordinate may be described as release state. On the pages that
  # exist to get somebody running it may never appear at all: a command that
  # installs nothing is worse than no command. The pinned installation guide is
  # the one place the stand-in commands are shown, under a warning that says
  # what they are, so that the path can be read before it is real.
  @placeholder_coordinates ["0.0.0-placeholder", String.duplicate("0", 40)]
  @pages_that_get_you_running ["/", "/docs", "/campaigns", "/proofs"]

  # This release installs and runs at a terminal. Any page that hints at a
  # journey beginning on a handheld device is describing something that does
  # not exist. (Engineering notes about narrow screens are not published words
  # and are not read here.)
  @absent_journey ["phone", "mobile", "tablet", "ios", "android app", "no terminal"]

  # Hermes can be run somewhere other than the reader's own machine. Naming a
  # hosted one without the qualifier reads as an offer this release cannot make.
  @hosted_path "portal.nousresearch.com"
  @hosted_qualifier "not yet a separately certified Techtree execution environment"

  # What a trial costs depends on a provider's prices and on how a run goes.
  # Any figure on this site would be a quote, and this site cannot give one.
  @priced_claim [
    ~r/\$\s*\d/,
    ~r/\b\d+(\.\d+)?\s*(usd|dollars?|cents?)\b/i
  ]

  # Describing the install-time report is optional. Describing it honestly is
  # not: the one answer a reader must never be offered is to stop the source
  # from being read at all. The word is looked for as prose — a name with a dot
  # in front of it is one module calling another, not a sentence a reader ever
  # sees.
  @report_described ~r/(?<![.\w])scan(s|ned|ning|ner)?\b/i
  @never_disable "Never turn the scanning off."

  # A page that hands a reader the command that installs the plugin has said
  # enough about installing to owe them the verdict that command will produce,
  # in the words it was decided in.
  @install_command "hermes plugins install"
  @scan_section [
    "What the security scan will say",
    "This plugin comes back at caution, with five findings in three families.",
    "A caution verdict is yours to answer.",
    "Hermes stops, shows you the findings, and installs nothing until a person confirms.",
    "Never turn the scanning off."
  ]

  # A pinned address is the whole promise: what a reader reads today is what
  # they get tomorrow. A branch, a tag, or a stand-in revision is not one.
  @repository_address ~r|https://github\.com/[^"\s<>]+|
  @pinned_address ~r|\Ahttps://github\.com/[\w.-]+/[\w.-]+/tree/[0-9a-f]{40}\z|

  # The one GitHub address that is informational rather than installable: the
  # verifiers hover card links the library's home (founder ruling 2026-08-26).
  # Nothing a reader installs is ever taken from it, so the immutable-revision
  # rule does not apply — and nothing else may join this list without the same
  # kind of ruling.
  @informational_addresses ["https://github.com/PrimeIntellect-ai/verifiers"]
  @unset_revision String.duplicate("0", 40)

  # The words a reader hands to their agent are decided copy, not a paraphrase
  # this suite is free to drift away from. One prompt is written once and shown
  # wherever the agent path is offered, so every page carrying it carries all of
  # it — read here with the line breaks taken out, because a page renders the
  # prompt as the block a reader copies.
  @agent_prompt "Read the pinned Techtree installation guide at https://techtree.sh/start. " <>
                  "If the guide says no installable release is active, stop and tell me. " <>
                  "Otherwise, use only the exact plugin commit and CLI version published by " <>
                  "the active release. Explain the prerequisites, the expected Hermes scanner " <>
                  "findings, what may spend model tokens, and what stays local. Ask before: " <>
                  "1. installing the Techtree plugin; 2. installing the Techtree CLI; or " <>
                  "3. starting a comparison that spends tokens. After the plugin is enabled, " <>
                  "tell me when Hermes must be restarted. Then run Techtree Doctor, obtain " <>
                  "the Hello World starter Skill, and prepare the comparison. Stop before " <>
                  "spending until I approve it. Do not upload my local evaluation artifacts."

  # The three promises inside the prompt that a rewrite must never lose: it asks
  # before it installs, it asks before it spends, and it never sends the
  # reader's own artifacts anywhere.
  @agent_prompt_promises [
    "Ask before: 1. installing the Techtree plugin; 2. installing the Techtree CLI; or " <>
      "3. starting a comparison that spends tokens.",
    "Stop before spending until I approve it.",
    "Do not upload my local evaluation artifacts."
  ]

  @agent_path_heading "Give this to your Hermes agent"
  @alternate_path_heading "Prefer installing it yourself?"

  @alternate_path [
    "Prefer installing it yourself?",
    "Install the exact pinned Hermes plugin shown below.",
    "Restart Hermes.",
    "Ask: “Set up Techtree and run the Hello World Climb.”"
  ]

  @hermes_introduction [
    "Hermes is an open-source agent made by Nous Research.",
    "Nous Portal provides model access, hosted tools, and cloud-hosted Hermes " <>
      "under one account.",
    # The address is a link, so the sentence's full stop sits outside it.
    "Explore it at https://portal.nousresearch.com/",
    "Techtree Hello World currently requires a Hermes host where you can install the " <>
      "plugin and CLI, access a terminal, run Docker, and authenticate with Prime.",
    "The Nous Portal cloud-hosted path is not yet a separately certified Techtree " <>
      "execution environment."
  ]

  # Decision 0035. Every other check here removes a claim; this one requires
  # one. What v0.1 is — a proof of concept for a stack of three independent
  # parts — is the frame around everything else the site says, and the way it
  # goes wrong is not a banned word appearing but the frame quietly going
  # missing, leaving a reader who has been told what the software does to
  # decide for themselves what it amounts to.
  @proof_of_concept ~r/\bproof[\s-]of[\s-]concept\b/i

  # Two of the three parts are somebody else's work, so each is named with the
  # project that made it. A proof of concept that reads as though we built the
  # whole stack is the same class of overclaim as any other.
  # The `u` modifier matters: without it the typographic apostrophe is three
  # bytes the character class would try to match one at a time.
  @stack_attribution [
    ~r/Prime\s+Intellect[’']s\s+Verifiers/iu,
    ~r/Nous\s+Research[’']s\s+Hermes/iu,
    ~r/Techtree\s+as\s+the\s+campaign\s+kernel/iu
  ]

  # "Stack" is the word that tells a reader where the seams are: an engine, a
  # host and a container, each pinned, and a release that is only as
  # reproducible as those pins. A frame that leaves that out is half the ruling.
  @stack_seams ~r/only\s+as\s+reproducible\s+as\s+those\s+pins/i

  # The pages that say what this release is: the front page a stranger lands
  # on, the documentation they read before running anything, and the page that
  # shows a real result. The last one was missing and that is how two capability
  # claims reached it - it draws an exact score, which is the one place a reader
  # most needs to be told what the number is and is not.
  @pages_that_say_what_this_is ["/", "/docs", "/proofs"]

  describe "every page, with a release being served" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
      Importer.import!(CatalogFixture.root())
      :ok
    end

    test "no page claims the work never leaves the machine", %{conn: conn} do
      refute_unqualified_privacy(rendered(conn, @pages))
    end

    test "no page says an account is not needed without saying whose", %{conn: conn} do
      refute_unscoped_account(rendered(conn, @pages))
    end

    test "no page claims anyone but the participant witnessed a run", %{conn: conn} do
      refute_dishonest_attestation(rendered(conn, @pages))
    end

    test "no page calls the pinned subject model the reader's own", %{conn: conn} do
      refute_blurred_model(rendered(conn, @pages))
    end

    test "no page promises the guided revision will work", %{conn: conn} do
      refute_promised_revision(rendered(conn, @pages))
    end

    test "the Climb page says a proposal may be unusable or may not help", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/climbs/hello-world-climb")
      text = visible_text(html)

      assert text =~ "Your own agent proposes one revision."
      assert text =~ "Techtree tests it"
      assert text =~ "A proposal may be unusable, or may run and fail to improve the score"
    end

    test "no page promises the starter Skill a score", %{conn: conn} do
      refute_exact_score_claim(rendered(conn, @pages))
    end

    test "no page calls the introductory Climb a benchmark", %{conn: conn} do
      refute_forbidden_name(rendered(conn, @pages))
    end

    test "the pages that say what this release is carry the whole frame", %{conn: conn} do
      require_proof_of_concept(rendered(conn, @pages_that_say_what_this_is))
    end

    test "the Climb page states the starter Skill's calibration in the approved words",
         %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/climbs/hello-world-climb")

      assert visible_text(html) =~
               "intentionally incomplete and calibrated to solve roughly two-thirds " <>
                 "of the toy tasks. Individual runs may vary."
    end

    test "no page offers a hosted Hermes without saying what it is not yet", %{conn: conn} do
      refute_uncertified_hosting(rendered(conn, @pages))
    end

    test "no page describes a journey that starts on a handheld device", %{conn: conn} do
      refute_absent_journey(rendered(conn, @pages))
    end

    test "no page puts a figure on what a trial costs", %{conn: conn} do
      refute_priced_claim(rendered(conn, @pages))
    end

    test "no page shows a plugin address that could move under the reader", %{conn: conn} do
      refute_moving_address(markup(conn, @pages))
    end

    test "every page offering the agent path carries the prompt as it was written",
         %{conn: conn} do
      offering =
        for {label, text} <- rendered(conn, @install_paths),
            String.contains?(text, @agent_path_heading) do
          assert text =~ @agent_prompt, "#{label} does not carry the prompt word for word"

          for promise <- @agent_prompt_promises do
            assert String.contains?(text, promise),
                   "#{label} does not carry #{inspect(promise)} word for word"
          end

          label
        end

      assert offering != [], "no page offered the agent path, so nothing was checked"
    end

    test "every page offering the other path carries its three steps as they were written",
         %{conn: conn} do
      offering =
        for {label, text} <- rendered(conn, @install_paths),
            String.contains?(text, @alternate_path_heading) do
          for line <- @alternate_path do
            assert text =~ line, "#{label} does not carry #{inspect(line)} word for word"
          end

          label
        end

      assert offering != [], "no page offered the other path, so nothing was checked"
    end

    test "every page saying what Hermes is says it as it was written", %{conn: conn} do
      for {label, text} <- rendered(conn, @pages), text =~ "New to Hermes Agent?" do
        for line <- @hermes_introduction do
          assert text =~ line, "#{label} does not carry #{inspect(line)} word for word"
        end
      end
    end

    test "no page describes the install-time report without saying it stays on",
         %{conn: conn} do
      require_never_disable(rendered(conn, @pages))
    end

    test "every page that hands out the install command says what the report will say",
         %{conn: conn} do
      offering =
        for {label, text} <- rendered(conn, @install_paths),
            String.contains?(text, @install_command) do
          for line <- @scan_section do
            assert String.contains?(text, line),
                   "#{label} offers the install command without #{inspect(line)}"
          end

          label
        end

      assert offering != [], "no page offered the install command, so nothing was checked"
    end

    test "the pages that describe privacy say where the model calls go", %{conn: conn} do
      silent =
        for {label, text} <- rendered(conn, ["/", "/start", "/proofs/local"]),
            not (text =~ @privacy_names_the_calls and text =~ @privacy_names_the_recipient),
            do: label

      assert silent == [],
             "these pages describe what stays on the reader's machine without saying that " <>
               "model calls go to the selected provider: #{Enum.join(silent, ", ")}"
    end

    test "every page stating a Climb's publication terms says this release publishes nothing",
         %{conn: conn} do
      showing = require_publishes_nothing(rendered(conn, @pages))

      assert showing != [],
             "no page stated the publication terms, so nothing was checked"
    end

    test "no page offers a part of a result this release does not have", %{conn: conn} do
      refute_offered_publication(rendered(conn, @pages))
    end

    test "no page hands a reader a stand-in coordinate to run", %{conn: conn} do
      refute_placeholder_coordinates(markup(conn, @pages_that_get_you_running))
    end

    test "the page a reader is sent to for a proof says what is and is not there",
         %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/proofs")
      text = visible_text(html)

      # Founder ruling 2026-08-26: the page leads with the real certified
      # example — and still says plainly that a reader cannot publish here yet.
      assert text =~ "Example Baseline vs. Instructional Skill"
      assert text =~ "Participant-attested"
      assert text =~ "arrives in a later release"
      assert text =~ "techtree proof verify path/to/result-bundle"

      # Every coordinate it does show is one the served release publishes.
      assert text =~ CatalogFixture.campaign_digest()
      assert text =~ "prime · qwen/qwen3.7-flash"
    end
  end

  describe "every page, with nothing imported" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
    end

    test "an empty release makes no claim a full one may not", %{conn: conn} do
      sources = rendered(conn, @pages_without_catalog)

      refute_unqualified_privacy(sources)
      refute_unscoped_account(sources)
      refute_dishonest_attestation(sources)
      refute_blurred_model(sources)
      refute_promised_revision(sources)
      refute_exact_score_claim(sources)
      refute_forbidden_name(sources)
      refute_uncertified_hosting(sources)
      refute_priced_claim(sources)
      refute_absent_journey(sources)
      refute_offered_publication(sources)
      require_never_disable(sources)
      refute_moving_address(markup(conn, @pages_without_catalog))
      require_proof_of_concept(rendered(conn, @pages_that_say_what_this_is))
    end
  end

  describe "the repository's own front page" do
    test "it says what this release is, the way the pages do" do
      require_proof_of_concept([{"README.md", File.read!("README.md")}])
    end
  end

  describe "the words behind the pages" do
    test "no module the pages are written in carries a claim a page may not" do
      sources = page_sources()

      assert sources != []

      refute_unqualified_privacy(sources)
      refute_unscoped_account(sources)
      refute_dishonest_attestation(sources)
      refute_blurred_model(sources)
      refute_promised_revision(sources)
      refute_exact_score_claim(sources)
      refute_forbidden_name(sources)
      refute_uncertified_hosting(sources)
      refute_priced_claim(sources)
      refute_offered_publication(sources)
      require_never_disable(sources)
    end

    test "the published installation contract carries no claim a page may not" do
      sources = bootstrap_sources()

      assert sources != []

      refute_unqualified_privacy(sources)
      refute_unscoped_account(sources)
      refute_dishonest_attestation(sources)
      refute_blurred_model(sources)
      refute_promised_revision(sources)
      refute_exact_score_claim(sources)
      refute_forbidden_name(sources)
      refute_uncertified_hosting(sources)
      refute_priced_claim(sources)
    end
  end

  # -- The checks -----------------------------------------------------------

  defp refute_unqualified_privacy(sources) do
    for {label, text} <- sources, claim <- @unqualified_privacy do
      for window <- windows_around(text, claim) do
        assert window =~ @privacy_names_the_calls and window =~ @privacy_names_the_recipient,
               """
               #{label} says #{inspect(claim)} without saying, nearby, that model calls \
               go to the selected provider under that provider's policies.
               """
      end
    end
  end

  defp refute_unscoped_account(sources) do
    for {label, text} <- sources do
      refute text =~ @unscoped_account,
             "#{label} says an account is not required without saying it is the Techtree one"
    end
  end

  defp refute_promised_revision(sources) do
    for {label, text} <- sources, pattern <- @promised_revision do
      refute text =~ pattern,
             "#{label} matches #{inspect(pattern)}: the guided revision is one proposal, " <>
               "tested honestly, not an outcome this site can promise"
    end
  end

  defp refute_blurred_model(sources) do
    for {label, text} <- sources do
      refute text =~ @blurred_model,
             "#{label} says \"your own model\": the model the agent under test answers " <>
               "with is pinned by the Campaign, not chosen by the reader"
    end
  end

  defp refute_dishonest_attestation(sources) do
    for {label, text} <- sources, pattern <- @dishonest_attestation do
      refute text =~ pattern,
             "#{label} matches #{inspect(pattern)}: only the participant attests a local run"
    end
  end

  defp refute_exact_score_claim(sources) do
    for {label, text} <- sources, pattern <- @exact_score_claim do
      refute text =~ pattern, "#{label} matches #{inspect(pattern)}: the public claim is a band"
    end
  end

  defp refute_forbidden_name(sources) do
    for {label, text} <- sources do
      refute text =~ @forbidden_name, "#{label} uses a name this release does not publish"
    end
  end

  # A template wraps its lines where the formatter puts them, so this one claim
  # is read with the line breaks taken out: the sentence is what matters, not
  # the column it happens to end in.
  defp refute_uncertified_hosting(sources) do
    for {label, source} <- sources,
        text = String.replace(source, ~r/\s+/, " "),
        String.contains?(text, @hosted_path) do
      assert String.contains?(text, @hosted_qualifier),
             "#{label} points a reader at a hosted Hermes without saying that it is " <>
               "not yet a separately certified place to run a Climb"
    end
  end

  defp refute_absent_journey(sources) do
    for {label, text} <- sources, word <- @absent_journey do
      refute String.downcase(text) =~ word,
             "#{label} says #{inspect(word)}: this release is installed and run at a terminal"
    end
  end

  defp refute_priced_claim(sources) do
    for {label, text} <- sources, pattern <- @priced_claim do
      refute text =~ pattern,
             "#{label} matches #{inspect(pattern)}: what a trial costs is set by the " <>
               "reader's provider, and this site cannot quote it"
    end
  end

  # Read with the line breaks taken out, so that a sentence a template wrapped
  # is still one sentence.
  defp require_never_disable(sources) do
    for {label, source} <- sources,
        text = String.replace(source, ~r/\s+/, " "),
        text =~ @report_described do
      assert String.contains?(text, @never_disable),
             "#{label} describes the install-time report without telling a reader to " <>
               "leave it switched on"
    end
  end

  # Decision 0035, in three parts, because a surface can lose any one of them
  # on its own: the frame, the attribution of the two parts that are not ours,
  # and what the release is pinned to.
  defp require_proof_of_concept(sources) do
    for {label, source} <- sources, text = String.replace(source, ~r/\s+/, " ") do
      assert text =~ @proof_of_concept,
             "#{label} says what this release is without calling it a proof of concept"

      for pattern <- @stack_attribution do
        assert text =~ pattern,
               "#{label} does not match #{inspect(pattern)}: the stack is three parts and " <>
                 "two of them are somebody else's work"
      end

      assert text =~ @stack_seams,
             "#{label} does not say that the release is only as reproducible as the " <>
               "versions it pins"
    end
  end

  defp refute_offered_publication(sources) do
    for {label, text} <- sources, pattern <- @offered_publication do
      refute text =~ pattern,
             "#{label} matches #{inspect(pattern)}: this release publishes nothing, " <>
               "receives nothing, and has no result of anyone's to hand over"
    end
  end

  defp refute_placeholder_coordinates(sources) do
    for {label, markup} <- sources, coordinate <- @placeholder_coordinates do
      refute String.contains?(markup, coordinate),
             "#{label} shows #{coordinate}, which is a stand-in rather than a release"
    end
  end

  defp refute_moving_address(sources) do
    for {label, markup} <- sources,
        address <- addresses(markup),
        address not in @informational_addresses do
      assert address =~ @pinned_address,
             "#{label} shows #{address}, which is not one immutable revision"

      refute String.contains?(address, @unset_revision),
             "#{label} shows #{address}, which is a stand-in rather than a release"
    end
  end

  defp addresses(markup) do
    @repository_address |> Regex.scan(markup) |> List.flatten()
  end

  # -- Where the words come from --------------------------------------------

  defp require_publishes_nothing(sources) do
    for {label, source} <- sources,
        text = String.replace(source, ~r/\s+/, " "),
        Enum.any?(@publication_terms, &String.contains?(text, &1)) do
      for half <- @publishes_nothing do
        assert String.contains?(text, half),
               "#{label} states what publication would mean without saying, beside it, " <>
                 "that this release publishes nothing: #{inspect(half)} is missing"
      end

      label
    end
  end

  defp rendered(conn, pages) do
    Enum.map(pages, fn page ->
      {:ok, _live, html} = live(conn, page)
      {"the page at #{page}", visible_text(html)}
    end)
  end

  # The same pages as markup, for the claims that live in an address rather
  # than in a sentence: a link's target is a promise a reader never reads.
  defp markup(conn, pages) do
    Enum.map(pages, fn page ->
      {:ok, _live, html} = live(conn, page)
      {"the page at #{page}", html}
    end)
  end

  defp page_sources do
    "lib/**/*.{ex,heex}"
    |> Path.wildcard()
    |> Enum.map(&{&1, File.read!(&1)})
  end

  # The installation contract this site publishes, and the one it is being
  # asked to publish next: a release candidate's words are read here before
  # approval, not after it becomes the served document.
  defp bootstrap_sources do
    ["priv/bootstrap/*.json", "priv/releases/*/bootstrap.json"]
    |> Enum.flat_map(&Path.wildcard/1)
    |> Enum.map(&{&1, File.read!(&1)})
  end

  # Every stretch of text around one claim, so a qualification two sentences
  # away still counts and one on a different page does not.
  defp windows_around(text, claim) do
    downcased = String.downcase(text)

    downcased
    |> :binary.matches(claim)
    |> Enum.map(fn {start, length} ->
      from = max(start - @privacy_qualification_window, 0)
      to = min(start + length + @privacy_qualification_window, byte_size(downcased))

      binary_part(downcased, from, to - from)
    end)
  end
end
