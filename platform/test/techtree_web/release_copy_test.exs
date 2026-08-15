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

  Every source of published words is scanned: each page as a reader sees it,
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
    "/start",
    "/climbs",
    "/climbs/hello-world-climb",
    "/proofs/local",
    "/protocol"
  ]

  @pages_without_catalog ["/", "/start", "/climbs", "/proofs/local", "/protocol"]

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

  @forbidden_name ~r/helloworldbench/i

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

  # A pinned address is the whole promise: what a reader reads today is what
  # they get tomorrow. A branch, a tag, or a stand-in revision is not one.
  @repository_address ~r|https://github\.com/[^"\s<>]+|
  @pinned_address ~r|\Ahttps://github\.com/[\w.-]+/[\w.-]+/tree/[0-9a-f]{40}\z|
  @unset_revision String.duplicate("0", 40)

  # The words a reader hands to their agent are decided copy, not a paraphrase
  # this suite is free to drift away from.
  @agent_prompt "Read the pinned Techtree installation guide at https://techtree.sh/start. " <>
                  "Review the exact GitHub plugin release and installation commands with me. " <>
                  "Ask for my approval before installing software or spending model credits. " <>
                  "Install and enable the Techtree Hermes plugin, tell me when Hermes must be " <>
                  "restarted, then use the plugin to install and verify the Techtree CLI and " <>
                  "run the Hello World Climb. Do not upload my local evaluation artifacts."

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

    test "the pages offering the agent path carry the prompt as it was written",
         %{conn: conn} do
      for {label, text} <- rendered(conn, ["/", "/start"]) do
        assert text =~ @agent_prompt, "#{label} does not carry the prompt word for word"
      end
    end

    test "the pages offering the other path carry its three steps as they were written",
         %{conn: conn} do
      for {label, text} <- rendered(conn, ["/?install=me", "/start?install=me"]) do
        for line <- @alternate_path do
          assert text =~ line, "#{label} does not carry #{inspect(line)} word for word"
        end
      end
    end

    test "every page saying what Hermes is says it as it was written", %{conn: conn} do
      for {label, text} <- rendered(conn, @pages), text =~ "New to Hermes Agent?" do
        for line <- @hermes_introduction do
          assert text =~ line, "#{label} does not carry #{inspect(line)} word for word"
        end
      end
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
      refute_moving_address(markup(conn, @pages_without_catalog))
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

  defp refute_moving_address(sources) do
    for {label, markup} <- sources, address <- addresses(markup) do
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
