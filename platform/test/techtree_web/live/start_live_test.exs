defmodule TechtreeWeb.StartLiveTest do
  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture

  describe "with a release published" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
      Importer.import!(CatalogFixture.root())
      :ok
    end

    test "the agent path is the one open by default", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/start")

      assert html =~ "Give this to your Hermes agent"
      refute html =~ "Prefer installing it yourself?"
    end

    test "the guide shows every command this release pins, whoever is installing",
         %{conn: conn} do
      for address <- [~p"/start", ~p"/start?install=me"] do
        {:ok, _live, html} = live(conn, address)

        assert html =~ "hermes plugins install regents-ai/techtree-hermes --ref"
        assert html =~ "hermes plugins doctor techtree --ci"
        assert html =~ "uv tool install --python 3.12 techtree==0.0.0-placeholder"
      end
    end

    test "the rendered install command is the pinned coordinate, argument for argument",
         %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/start")

      assert ("hermes plugins install regents-ai/techtree-hermes --ref " <>
                String.duplicate("0", 40) <> " --enable") in commands(html)
    end

    test "the agent path says the agent asks first and hands back a run identifier",
         %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/start")
      text = visible_text(html)

      assert text =~ "It asks before it installs anything, runs anything, or spends anything."
      assert text =~ "hands back a run identifier instead of making you wait"
    end

    test "the other path says a plugin is installed only with your approval", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/start?install=me")

      assert visible_text(html) =~
               "Installing a plugin takes your explicit approval, so an agent cannot put " <>
                 "itself in a position to run trials."
    end

    test "the guide says Hermes has to be there first and a terminal is needed",
         %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/start")
      text = visible_text(html)

      assert text =~ "Hermes 0.20.1 or newer, already installed and working."
      assert text =~ "Techtree installs and runs on the machine in front of you, at a terminal."
    end

    test "neither path suggests a first installation without a terminal", %{conn: conn} do
      for address <- [~p"/start", ~p"/start?install=me"] do
        {:ok, _live, html} = live(conn, address)
        text = html |> visible_text() |> String.downcase()

        for elsewhere <- ["phone", "mobile", "tablet", "no terminal", "without a terminal"] do
          refute text =~ elsewhere, "#{address} points the first installation at a #{elsewhere}"
        end
      end
    end

    test "every command shown is one a reader can copy as it stands", %{conn: conn} do
      for address <- [~p"/start", ~p"/start?install=me"] do
        {:ok, _live, html} = live(conn, address)

        for command <- commands(html) do
          refute command =~ ~r/\bmain\b/, "#{command} pins a moving branch"
          refute command =~ ~r/\blatest\b/, "#{command} pins a moving version"

          for interpolation <- ["$", "`", "|", "&&", ";", ">", "<", "$(", "*"] do
            refute String.contains?(command, interpolation),
                   "#{command} needs a shell to mean what it says"
          end
        end
      end
    end

    test "the path for someone installing it themselves is the one the address can ask for",
         %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/start?install=me")
      text = visible_text(html)

      assert text =~ "Prefer installing it yourself?"
      assert text =~ "Install the exact pinned Hermes plugin shown below."
      assert text =~ "Restart Hermes."
      assert text =~ "Ask: “Set up Techtree and run the Hello World Climb.”"

      refute text =~ "Give this to your Hermes agent"
    end

    test "an address that names no path opens the agent one", %{conn: conn} do
      {:ok, _live, html} = live(conn, "/start?install=whatever")

      assert html =~ "Give this to your Hermes agent"
      refute html =~ "Prefer installing it yourself?"
    end

    test "the switcher swaps which path is in front", %{conn: conn} do
      {:ok, live, _html} = live(conn, ~p"/start")

      terminal = live |> element(~s|a[href="/start?install=me"]|) |> render_click()

      assert terminal =~ "Prefer installing it yourself?"
      refute terminal =~ "Give this to your Hermes agent"

      agent = live |> element(~s|a[href="/start?install=agent"]|) |> render_click()

      assert agent =~ "Give this to your Hermes agent"
      refute agent =~ "Prefer installing it yourself?"
    end

    test "the switcher is an ordinary link, so it works without a live connection",
         %{conn: conn} do
      html = conn |> get(~p"/start") |> html_response(200)

      assert html =~ ~s|href="/start?install=me"|
      assert html =~ ~s|href="/start?install=agent"|

      switched = conn |> get(~p"/start?install=me") |> html_response(200)

      assert switched =~ "Prefer installing it yourself?"
    end

    test "the switcher marks the path that is open", %{conn: conn} do
      {:ok, live, _html} = live(conn, ~p"/start")

      assert live |> element(~s|a[href="/start?install=agent"][aria-current]|) |> has_element?()
      refute live |> element(~s|a[href="/start?install=me"][aria-current]|) |> has_element?()
    end

    test "either path says what the introductory Climb is and is not", %{conn: conn} do
      for address <- [~p"/start", ~p"/start?install=me"] do
        {:ok, live, html} = live(conn, address)

        assert html =~
                 "A toy introductory demonstration of the mechanism, " <>
                   "not a measure of broad capability."

        assert live |> element(~s|a[href="/climbs/hello-world-climb"]|) |> has_element?()
      end
    end

    test "either path says what the machine needs and where the model calls go",
         %{conn: conn} do
      for address <- [~p"/start", ~p"/start?install=me"] do
        {:ok, _live, html} = live(conn, address)
        text = visible_text(html)

        assert text =~ "macOS or Linux"
        assert text =~ "Hermes 0.20.1 or newer"
        assert text =~ "the installer provides its own Python 3.12"
        assert text =~ "uv 0.10.2 or newer"
        assert text =~ "Docker Installed, and running before a trial starts."
        assert text =~ "a key from your model provider"

        assert text =~
                 "Techtree does not upload your recordings, your results, or the work you submit."

        assert text =~
                 "The agent under test makes real model calls, and those are sent to the " <>
                   "model provider you selected, under that provider’s policies."

        assert text =~ "carries your Skill text and a sanitized summary of the run"
      end
    end

    test "neither path puts a number on what a run costs", %{conn: conn} do
      for address <- [~p"/start", ~p"/start?install=me"] do
        {:ok, _live, html} = live(conn, address)
        text = visible_text(html)

        refute text =~ ~r/\$\s*\d/
        refute text =~ ~r/\b\d+(\.\d+)?\s*(usd|dollars?|cents?)\b/i
      end
    end

    test "the guide says who is billed for a trial and that nothing paid starts unasked",
         %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/start")
      text = visible_text(html)

      assert text =~ "billed to the provider account you use"
      assert text =~ "Techtree charges nothing and holds no balance."
      assert text =~ "the most that run may cost"
      assert text =~ "waits for you to say yes"
    end

    test "the placeholder release is labelled where the commands are shown", %{conn: conn} do
      for address <- [~p"/start", ~p"/start?install=me"] do
        {:ok, _live, html} = live(conn, address)

        assert html =~ "not a real release yet"
        assert html =~ "They install nothing."
      end
    end

    test "a placeholder release is given no plugin release address at all", %{conn: conn} do
      for address <- [~p"/start", ~p"/start?install=me"] do
        {:ok, _live, html} = live(conn, address)

        refute html =~ "github.com"

        assert visible_text(html) =~
                 "This release does not name a published plugin revision yet"
      end
    end

    test "the prompt sends the agent to this site while the revision is a stand-in",
         %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/start")

      assert visible_text(html) =~
               "Read the pinned Techtree installation guide at https://techtree.sh/start."
    end

    test "no command is presented as a line to be run by the site", %{conn: conn} do
      for address <- [~p"/start", ~p"/start?install=me"] do
        {:ok, _live, html} = live(conn, address)

        refute html =~ "curl"
        refute html =~ "| sh"
        refute html =~ "sudo"
      end
    end
  end

  describe "with a release whose coordinates are real" do
    @describetag :tmp_dir

    setup %{tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)

      CatalogFixture.rewrite_bootstrap!(bundle, &CatalogFixture.concrete_release/1)
      CatalogFixture.use_bundle(bundle)
      Importer.import!(bundle)

      {:ok, revision: String.duplicate("a", 40)}
    end

    test "the prompt names the exact pinned plugin release instead of this site",
         %{conn: conn, revision: revision} do
      {:ok, _live, html} = live(conn, ~p"/start")
      text = visible_text(html)

      assert text =~
               "Read the pinned Techtree installation guide at " <>
                 "https://github.com/regents-ai/techtree-hermes/tree/#{revision}."

      refute text =~ "https://techtree.sh/start"
    end

    test "the guide links that same release and nothing that can move",
         %{conn: conn, revision: revision} do
      {:ok, live, html} = live(conn, ~p"/start")

      assert live
             |> element(
               ~s|a[href="https://github.com/regents-ai/techtree-hermes/tree/#{revision}"]|
             )
             |> has_element?()

      refute html =~ "not a real release yet"
      refute visible_text(html) =~ "does not name a published plugin revision yet"
    end
  end

  describe "with nothing published" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
    end

    test "the page says so calmly and shows no invented commands", %{conn: conn} do
      for address <- [~p"/start", ~p"/start?install=me"] do
        {:ok, _live, html} = live(conn, address)

        assert html =~ "Installation details are not published on this site yet."
        refute html =~ "uv tool install"
        refute html =~ "hermes plugins install"
      end
    end
  end

  # The commands as a reader sees them, taken out of the blocks they are shown
  # in rather than off the payload they were built from: what is checked here
  # has to be the line someone would copy.
  defp commands(html) do
    ~r|<pre class="command__block"><code>(.*?)</code></pre>|s
    |> Regex.scan(html, capture: :all_but_first)
    |> List.flatten()
    |> Enum.map(&as_copied/1)
  end

  # The characters a reader's clipboard would receive, not the ones the markup
  # spells them with: a redirection escaped as an entity is still a redirection.
  defp as_copied(command) do
    command
    |> String.replace("&lt;", "<")
    |> String.replace("&gt;", ">")
    |> String.replace("&quot;", "\"")
    |> String.replace("&#39;", "'")
    |> String.replace("&amp;", "&")
  end
end
