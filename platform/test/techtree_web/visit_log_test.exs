defmodule TechtreeWeb.VisitLogTest do
  # Invariant: whatever a caller or browser sends, a visit line holds only the
  # site's own names and shapes. Headers, reported lines and event fields that do
  # not fit are dropped or written as `other`, never copied into the log.
  use ExUnit.Case, async: true
  use ExUnitProperties

  import Plug.Test, only: [conn: 2]
  import Plug.Conn, only: [put_req_header: 3]

  alias TechtreeWeb.{VisitLog, VisitLogController}

  @where ~r/\A[A-Za-z0-9_.:\/@* -]{1,120}\z/
  @outcome ~r/\A[a-z0-9_]{1,48}\z/
  @visit ~r/\A[A-Za-z0-9_-]{22}\z/

  property "an event keeps only fitting where and outcome values" do
    check all(
            where <- one_of([string(:printable), string(:ascii)]),
            outcome <- string(:printable)
          ) do
      event = VisitLog.event("press", where, outcome, 3)

      assert Map.keys(event) |> Enum.sort() == [:ms, :name, :outcome, :where]
      assert event.where == where or event.where == "other"
      assert event.outcome == outcome or event.outcome == "other"
      assert event.where =~ @where
      assert event.outcome =~ @outcome
    end
  end

  property "a request's surface, tool and visit come only from fitting headers" do
    check all(
            path <- member_of(["/api/v1/catalog", "/results/abc", "/"]),
            client <-
              one_of([
                string(:printable),
                member_of(["webmcp/techtree_climbs", "regents-cli/1.10.18 techtree climbs"])
              ]),
            visit <- one_of([string(:printable), string(:alphanumeric, length: 22)])
          ) do
      conn =
        conn(:get, path)
        |> put_req_header("x-regent-client", client)
        |> put_req_header("x-regent-visit", visit)
        |> VisitLog.call([])

      surface = Logger.metadata()[:surface]
      assert surface in ~w(page webmcp cli agent_http)
      caller = VisitLog.caller(conn)

      assert (path != "/api/v1/catalog" and caller == nil) or caller in ~w(webmcp other none) or
               caller =~ ~r/\A[a-z][a-z0-9._-]{0,31}\/[0-9][0-9A-Za-z.+-]{0,31}\z/

      assert conn.assigns.visit == nil or conn.assigns.visit =~ @visit
      assert VisitLog.client(conn) == nil or VisitLog.client(conn) =~ @where

      case surface do
        "webmcp" ->
          assert "webmcp/" <> VisitLog.client(conn) == client

        "cli" ->
          assert String.starts_with?(client, "regents-cli/")

        "page" ->
          assert VisitLog.client(conn) == nil and
                   (path != "/api/v1/catalog" or conn.assigns.visit)

        "agent_http" ->
          assert VisitLog.client(conn) == nil and conn.assigns.visit == nil
      end
    end
  end

  test "an API call names the program that made it" do
    caller = fn sent ->
      Enum.reduce(sent, conn(:get, "/api/v1/catalog"), &put_req_header(&2, "x-regent-client", &1))
      |> VisitLog.call([])
      |> VisitLog.caller()
    end

    assert caller.(["regents-cli/1.10.18 notebooks run"]) == "regents-cli/1.10.18"
    assert caller.(["webmcp/techtree_climbs"]) == "webmcp"
    assert caller.(["my-agent/0.3.1"]) == "my-agent/0.3.1"
    assert caller.(["Mozilla/5.0 (X11)"]) == "other"
    assert caller.([]) == "none"
    assert conn(:get, "/results/abc") |> VisitLog.call([]) |> VisitLog.caller() == nil
  end

  test "a page's own script calling the API belongs to its visit, by header or cookie" do
    visit = String.duplicate("v", 22)
    api = fn -> conn(:get, "/api/v1/catalog") end

    for sent <- [
          put_req_header(api.(), "x-regent-visit", visit),
          Plug.Test.put_req_cookie(api.(), "_visit", visit)
        ] do
      conn = VisitLog.call(sent, [])
      assert {Logger.metadata()[:surface], conn.assigns.visit} == {"page", visit}
    end

    conn = VisitLog.call(api.(), [])
    assert {Logger.metadata()[:surface], conn.assigns.visit} == {"agent_http", nil}
  end

  property "the browser's reports keep only the lines a page can send, twenty at most" do
    sent =
      one_of([
        fixed_map(%{
          "name" =>
            member_of(["page.error", "tool.unsent", "press.unsent", "step", "visit.other"]),
          "where" =>
            one_of([
              string(:printable),
              member_of([
                "/results/abc",
                "/nowhere",
                "techtree_climbs",
                "buy",
                "sign_in_opened",
                "signed_in"
              ])
            ]),
          "outcome" =>
            one_of([
              string(:printable),
              member_of(~w(error unhandledrejection unreachable outcome_unknown lost))
            ])
        }),
        term()
      ])

    check all(lines <- list_of(sent, max_length: 30)) do
      kept = VisitLogController.lines(%{"lines" => lines}, "www.example.com")

      assert length(kept) <= 20

      for {name, where, outcome} <- kept do
        case name do
          "page.error" ->
            assert outcome in ~w(error unhandledrejection)

            assert where in ["/results/:bundle_digest", "unmatched"] or
                     where =~ ~r/\A\/[a-z\/:._-]*\z/

          "tool.unsent" ->
            assert outcome in ~w(unreachable outcome_unknown)
            assert where =~ ~r/\A[a-z][a-z0-9_]{0,63}\z/

          "press.unsent" ->
            assert outcome == "lost"
            assert where =~ ~r/\A[a-z][a-z0-9_]{0,63}\z/

          "step" ->
            assert {where, outcome} == {"sign_in_opened", nil}
        end
      end
    end
  end

  property "an arrival names where it came from only by the site's own words" do
    words = VisitLog.sources() ++ ~w(site other_site direct)

    check all(
            referrer <-
              one_of([
                string(:printable),
                map(string(:alphanumeric), &"https://#{&1}.example/x?q=secret")
              ]),
            utm <-
              one_of([constant(nil), string(:printable), member_of(["chatgpt.com", "claude"])])
          ) do
      path = if utm, do: "/?" <> URI.encode_query(%{"utm_source" => utm}), else: "/"
      arrival = conn(:get, path) |> put_req_header("referer", referrer) |> VisitLog.arrival()

      assert arrival in words
      refute arrival =~ "secret"
    end
  end

  test "an arrival from an AI answer, a search, a post or nowhere" do
    from = fn headers, path ->
      Enum.reduce(headers, conn(:get, path), fn {key, value}, conn ->
        put_req_header(conn, key, value)
      end)
      |> VisitLog.arrival()
    end

    assert from.([{"referer", "https://chatgpt.com/c/abc"}], "/") == "chatgpt"
    assert from.([], "/docs?utm_source=chatgpt.com") == "chatgpt"
    assert from.([{"referer", "https://www.perplexity.ai/search?q=x"}], "/") == "perplexity"
    assert from.([{"referer", "https://gemini.google.com/app"}], "/") == "gemini"
    assert from.([{"referer", "https://www.google.com/"}], "/") == "google"
    assert from.([{"referer", "https://www.linkedin.com/feed/"}], "/") == "linkedin"
    assert from.([{"referer", "https://old.reddit.com/r/elixir"}], "/") == "reddit"
    assert from.([{"referer", "http://www.example.com/results"}], "/") == "site"
    assert from.([{"referer", "https://someones-blog.net/post"}], "/") == "other_site"
    assert from.([{"referer", "https://claude.ai/"}], "/?utm_source=newsletter") == "claude"
    assert from.([], "/") == "direct"
  end

  test "a visit that asks not to be tracked starts with no arrival" do
    opened = fn headers ->
      Enum.reduce(headers, conn(:get, "/docs"), fn {name, value}, conn ->
        put_req_header(conn, name, value)
      end)
      |> put_req_header("accept", "text/html")
      |> put_req_header("referer", "https://chatgpt.com/c/a-private-chat")
      |> VisitLog.call([])
    end

    tracked = opened.([])
    assert {tracked.assigns.arrival, tracked.assigns.gpc} == {"chatgpt", false}

    untracked = opened.([{"sec-gpc", "1"}])
    assert untracked.assigns.visit =~ @visit
    assert {untracked.assigns[:arrival], untracked.assigns.gpc} == {nil, true}
  end

  test "a page's own path is written as its route, and a page the site lacks as unmatched" do
    assert [
             {"page.error", "/results/:bundle_digest", "error"},
             {"page.error", "unmatched", "unhandledrejection"}
           ] =
             VisitLogController.lines(
               %{
                 "lines" => [
                   %{
                     "name" => "page.error",
                     "where" => "/results/a-private-result",
                     "outcome" => "error"
                   },
                   %{
                     "name" => "page.error",
                     "where" => "/no/such/page",
                     "outcome" => "unhandledrejection"
                   }
                 ]
               },
               "www.example.com"
             )
  end
end
