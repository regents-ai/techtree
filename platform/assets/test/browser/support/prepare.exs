# Everyone the walk's tests sign in as, made in the browser test database before
# the test server starts (playwright.config.ts), so no test runs a script while the
# others run: people, each with a session of their own; sessions of the team's one
# person; people with an agent paired; and sets of projects the team delivered. All
# of it goes to tmp/<partition>-walk/prepared.json, and a test takes the next one
# of a kind that no other test has taken (support/visitor.ts). There are three
# times as many of each as one walk takes, so the walk also runs with --repeat-each 3.
# Run from platform/ with the browser test server's environment.
unless Mix.env() == :test and
         String.starts_with?(System.get_env("MIX_TEST_PARTITION", ""), "browser"),
       do: raise("browser test database only")

Logger.configure(level: :warning)
{:ok, _} = Application.ensure_all_started([:postgrex, :ecto_sql, :ash, :ash_postgres])
{:ok, _} = Techtree.Repo.start_link()

alias Techtree.Accounts.SessionAuthority
alias Techtree.ProjectPackage

# Made fresh each run, so nothing an earlier run prepared or took is left.
walk = Path.expand("tmp/#{System.fetch_env!("MIX_TEST_PARTITION")}-walk")
File.rm_rf!(walk)
File.mkdir_p!(Path.join(walk, "taken"))

app_id = Application.fetch_env!(:techtree, :privy)[:app_id]
endpoint = Application.fetch_env!(:techtree, TechtreeWeb.Endpoint)
session_options = Plug.Session.init(Application.fetch_env!(:techtree, :session_options))

# The person's account, and the shared profile a real sign-in makes
# (RegentIdentity.ensure/1), with no name; returns the account's id.
account = fn person, wallet ->
  %{rows: [[id]]} =
    Techtree.Repo.query!(
      """
      INSERT INTO regent_names.platform_human_users
        (privy_user_id, wallet_address, wallet_addresses, created_at, updated_at)
      VALUES ($1, $2, $3, now(), now())
      ON CONFLICT (privy_user_id) DO UPDATE SET updated_at = now()
      RETURNING id
      """,
      [person, wallet, [wallet]]
    )

  Techtree.Repo.query!(
    """
    INSERT INTO regent_identity.profiles
      (id, app_id, privy_user_id, wallet_addresses, proof_issued_at, inserted_at, updated_at)
    VALUES (gen_random_uuid(), $1, $2, $3, $4, now(), now())
    ON CONFLICT (app_id, privy_user_id) DO UPDATE SET display_name = NULL, updated_at = now()
    """,
    [app_id, person, [wallet], System.system_time(:second)]
  )

  id
end

# A fresh session bound to the account, as the cookie a browser would hold. Each
# browser context needs its own: the site ends a session another browser presents
# after it has moved on.
session = fn id ->
  {:bootstrap, claim} = SessionAuthority.renew(nil)
  {:ok, :bind, claim} = SessionAuthority.sign_in(claim, id)

  conn =
    Plug.Test.conn(:get, "/")
    |> Map.put(:secret_key_base, endpoint[:secret_key_base])
    |> Plug.Session.call(session_options)
    |> Plug.Conn.fetch_session()

  conn =
    claim
    |> SessionAuthority.session()
    |> Enum.reduce(conn, fn {key, value}, conn -> Plug.Conn.put_session(conn, key, value) end)
    |> Plug.Conn.send_resp(200, "")

  %{name: session_options.key, value: conn.resp_cookies[session_options.key].value}
end

# A person of a test's own, signed in.
person = fn ->
  id = "did:privy:browser-" <> Ecto.UUID.generate()
  wallet = "0x" <> Base.encode16(:crypto.strong_rand_bytes(20), case: :lower)
  %{id: id, wallet: wallet, cookie: session.(account.(id, wallet))}
end

people = for _ <- 1..78, do: person.()

# The browser tests' person is one of the team (config/test.exs).
team_id = "did:privy:browser-test"
team_wallet = "0x" <> String.duplicate("b", 40)
team_account = account.(team_id, team_wallet)
team = for _ <- 1..18, do: %{id: team_id, wallet: team_wallet, cookie: session.(team_account)}

# A person of a test's own, signed in, with one agent paired under a name and
# wallet of its own, for a test that changes it.
agents =
  for _ <- 1..12 do
    signed_in = person.()
    suffix = 4 |> :crypto.strong_rand_bytes() |> Base.encode16(case: :lower)
    name = "Walk Agent #{suffix}"

    code =
      RegentAgents.issue_pairing_code!(actor: %RegentAgents.Person{privy_user_id: signed_in.id})

    RegentAgents.pair_agent!(code.code, name, :hermes,
      actor: %RegentAgents.Agent{wallet: "0x" <> String.duplicate(suffix, 5)}
    )

    Map.put(signed_in, :agent, name)
  end

# Three projects the team delivers to its own person, one for each verdict, and
# one more package written to a file for the team to upload.
admin = %RegentAgents.Person{privy_user_id: team_id, role: :admin}

cases = fn rows ->
  Enum.map(rows, fn {id, original, selected} ->
    %{"id" => id, "original_solved" => original, "selected_solved" => selected, "repeats" => 3}
  end)
end

candidate = fn name, solved, attempts, refused, selected ->
  %{
    "candidate" => name,
    "solved" => solved,
    "attempts" => attempts,
    "refused" => refused,
    "selected" => selected
  }
end

# The final test's figures, each consistent with its cases.
verdicts = %{
  "improved" => & &1,
  "inconclusive" => fn manifest ->
    manifest
    |> Map.merge(%{
      "title" => "Invoice triage",
      "success" => "Each invoice reaches the queue that pays it.",
      "verdict" => "inconclusive",
      "cases" =>
        cases.([
          {"invoice-from-a-new-supplier", 1, 3},
          {"credit-note-against-an-invoice-paid-last-year", 2, 3},
          {"invoice-in-two-currencies", 3, 2},
          {"duplicate-invoice", 1, 1},
          {"invoice-without-a-purchase-order", 2, 2},
          {"scanned-invoice", 1, 1}
        ]),
      "selection" => [
        candidate.("original", 10, 18, false, false),
        candidate.("rewrite", 13, 18, true, false),
        candidate.("skillopt", 12, 18, false, true)
      ]
    })
    |> Map.update!("summary", fn summary ->
      Map.merge(summary, %{
        "final_cases" => 6,
        "original" => %{"solved" => 10, "attempts" => 18},
        "selected" => %{"candidate" => "skillopt", "solved" => 12, "attempts" => 18},
        "difference" => 2,
        "p_value" => 0.31,
        "pass_bar" => 0.8,
        "pass_bar_met" => false,
        "regressions" => 1
      })
    end)
    |> put_in(["setup", "split", "final"], 6)
  end,
  "not_improved" => fn manifest ->
    manifest
    |> Map.merge(%{
      "title" => "Contract clause review",
      "success" => "Each clause that needs a lawyer is flagged.",
      "verdict" => "not_improved",
      "cases" =>
        cases.([{"clause-1", 3, 2}, {"clause-2", 2, 1}, {"clause-3", 2, 3}, {"clause-4", 1, 1}]),
      "selection" => [
        candidate.("original", 8, 12, false, false),
        candidate.("rewrite", 9, 12, false, true),
        candidate.("skillopt", 6, 12, true, false)
      ]
    })
    |> Map.update!("summary", fn summary ->
      Map.merge(summary, %{
        "final_cases" => 4,
        "original" => %{"solved" => 8, "attempts" => 12},
        "selected" => %{"candidate" => "rewrite", "solved" => 7, "attempts" => 12},
        "difference" => -1,
        "p_value" => nil,
        "pass_bar" => 0.75,
        "pass_bar_met" => false,
        "regressions" => 2
      })
    end)
    |> put_in(["setup", "split", "final"], 4)
  end
}

reports = %{
  "improved" => ProjectPackage.files()["report.md"],
  "inconclusive" => """
  # Invoice triage

  The selected Skill solved **12 of 18** final attempts, against 10 of 18 before.
  A difference this size can come from chance, and one case got worse.

  | Case | Original | Selected | What changed |
  | --- | --- | --- | --- |
  | credit-note-against-an-invoice-paid-last-year | 2 of 3 | 3 of 3 | It now finds the paid invoice before routing the credit note. |
  | invoice-in-two-currencies | 3 of 3 | 2 of 3 | It sometimes sends the invoice to the queue of its second currency. |

  > Chance level 0.05; the final test's p-value was 0.31, so the difference is within chance.
  """,
  "not_improved" => """
  # Contract clause review

  The selected Skill solved **7 of 12** final attempts, against 8 of 12 before.
  Two cases got worse, so the original Skill stays.
  """
}

projects =
  for n <- 1..6 do
    ids =
      Map.new(verdicts, fn {verdict, change} ->
        files = Map.put(ProjectPackage.files(), "report.md", reports[verdict])
        package = ProjectPackage.build(files: files, manifest: change)
        {:ok, project} = Techtree.Projects.deliver_project(team_id, package, actor: admin)
        {verdict, project.id}
      end)

    file = Path.join(walk, "upload-#{n}.tar.gz")
    File.write!(file, ProjectPackage.build(manifest: &Map.put(&1, "title", "Ticket tagging")))
    Map.merge(ids, %{"upload" => file, "upload_title" => "Ticket tagging"})
  end

File.write!(
  Path.join(walk, "prepared.json"),
  Jason.encode!(%{people: people, team: team, agents: agents, projects: projects})
)
