defmodule TechtreeWeb.ReleaseCopyTest do
  @moduledoc """
  The claims this site is not allowed to make.

  Five sentences are easy to write and wrong to publish: that a trial happens
  entirely on the reader's own machine, that entering needs no account at all,
  that anyone but the participant witnessed the run, that the reader picked the
  model the agent under test answers with, and that the introductory Skill
  scores a particular number. Each of them is close enough to the truth that it
  survives a careful edit, which is why it is checked here instead.

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
      refute_exact_score_claim(sources)
      refute_forbidden_name(sources)
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
      refute_exact_score_claim(sources)
      refute_forbidden_name(sources)
    end

    test "the published installation contract carries no claim a page may not" do
      sources = bootstrap_sources()

      assert sources != []

      refute_unqualified_privacy(sources)
      refute_unscoped_account(sources)
      refute_dishonest_attestation(sources)
      refute_blurred_model(sources)
      refute_exact_score_claim(sources)
      refute_forbidden_name(sources)
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

  # -- Where the words come from --------------------------------------------

  defp rendered(conn, pages) do
    Enum.map(pages, fn page ->
      {:ok, _live, html} = live(conn, page)
      {"the page at #{page}", visible_text(html)}
    end)
  end

  defp page_sources do
    "lib/**/*.{ex,heex}"
    |> Path.wildcard()
    |> Enum.map(&{&1, File.read!(&1)})
  end

  defp bootstrap_sources do
    "priv/bootstrap/*.json"
    |> Path.wildcard()
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
