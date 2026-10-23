defmodule TechtreeWeb.WalletBenchResultsTest do
  @moduledoc """
  A wallet test's full results as one zip: its results beside every file each
  of its tests recorded, each file exactly as recorded, and nothing when a
  stored file no longer matches its record.
  """

  use TechtreeWeb.ConnCase, async: false

  alias Techtree.WalletBench.Evidence
  alias Techtree.WalletBenchFixture

  setup do
    previous = Application.get_env(:techtree, Evidence)

    Application.put_env(:techtree, Evidence,
      endpoint: "https://evidence.example",
      bucket: "evidence",
      region: "auto",
      access_key_id: "test",
      secret_access_key: "test",
      req_options: [plug: {Req.Test, Evidence}]
    )

    on_exit(fn -> Application.put_env(:techtree, Evidence, previous) end)

    tests = WalletBenchFixture.seed!()
    %{tests: tests, files: Map.new(WalletBenchFixture.files(tests))}
  end

  defp store(files) do
    Req.Test.stub(Evidence, fn conn ->
      key = conn.path_info |> tl() |> Enum.map_join("/", &URI.decode/1)
      Plug.Conn.send_resp(conn, 200, Map.fetch!(files, key))
    end)
  end

  test "the zip holds the results and every recorded file, byte for byte", %{
    conn: conn,
    tests: tests,
    files: files
  } do
    store(files)
    conn = get(conn, ~p"/wallet-bench/#{tests.passed.id}/results.zip")

    folder = "wallet-test-#{String.slice(tests.passed.id, 0, 8)}"
    assert response_content_type(conn, :zip) =~ "application/zip"

    assert get_resp_header(conn, "content-disposition") == [
             ~s(attachment; filename="#{folder}.zip")
           ]

    {:ok, entries} = :zip.unzip(response(conn, 200), [:memory])
    entries = Map.new(entries, fn {name, body} -> {List.to_string(name), body} end)

    results = Jason.decode!(entries["#{folder}/results.json"])

    assert %{"agent" => "Hermes Agent", "wallet_tool" => "Bankr", "status" => "Finished"} =
             results

    assert [%{"folder" => "T1a", "ruling" => %{"outcome" => "Pass"}}, %{"folder" => "T2"}] =
             results["tests"]

    for {key, body} <- files, String.contains?(key, tests.passed.id) do
      [_attempts, _id, turn, file] = String.split(key, "/")
      assert entries["#{folder}/#{turn}/#{file}"] == body
    end

    assert map_size(entries) == 1 + Enum.count(files, fn {key, _} -> key =~ tests.passed.id end)
  end

  # A stored file that no longer matches its record is found before the download
  # begins, wherever it falls in the zip: the visitor gets the error page.
  for {where, turn, file} <- [{"first", "T1a", "install.log"}, {"last", "T2", "session.jsonl"}] do
    test "a changed #{where} file gets the error page, not a broken zip", %{
      conn: conn,
      tests: tests,
      files: files
    } do
      key = Evidence.turn_key(tests.passed.id, unquote(turn), unquote(file))
      store(Map.update!(files, key, &(&1 <> "changed")))

      {status, _headers, body} =
        assert_error_sent 500, fn ->
          get(conn, ~p"/wallet-bench/#{tests.passed.id}/results.zip")
        end

      assert status == 500
      assert body =~ "Something went wrong"
      refute body =~ "PK"
    end
  end

  # A file that changes between the check and its own read ends the connection
  # before its bytes go out, and nothing is written after what was sent.
  test "a file that changes while the zip is sent ends the download", %{
    conn: conn,
    tests: tests,
    files: files
  } do
    key = Evidence.turn_key(tests.passed.id, "T2", "session.jsonl")
    reads = :counters.new(1, [])

    Req.Test.stub(Evidence, fn conn ->
      asked = conn.path_info |> tl() |> Enum.map_join("/", &URI.decode/1)
      if asked == key, do: :counters.add(reads, 1, 1)
      changed = asked == key and :counters.get(reads, 1) > 1
      body = if changed, do: files[asked] <> "changed", else: files[asked]
      Plug.Conn.send_resp(conn, 200, body)
    end)

    assert_raise RuntimeError, ~r/does not match the sha256 recorded with it/, fn ->
      get(conn, ~p"/wallet-bench/#{tests.passed.id}/results.zip")
    end

    # One response began, and no second one followed it.
    assert_received {:plug_conn, :sent}
    refute_received {:plug_conn, :sent}
  end

  # A single recorded file is held whole while it is sent, so it takes a place
  # like the zip does (security assessment of 19 Oct, finding 2).
  for {what, path} <- [{"the zip", "results.zip"}, {"a single file", "evidence/T2/session.jsonl"}] do
    test "with every download place taken, #{what} asks the visitor to try again", %{
      conn: conn,
      tests: tests,
      files: files
    } do
      store(files)
      parent = self()

      holders =
        for _place <- 1..4 do
          spawn_link(fn ->
            Registry.register(TechtreeWeb.ResultsDownloads, :download, nil)
            send(parent, :holding)
            receive do: (:done -> :ok)
          end)
        end

      for _holder <- holders, do: assert_receive(:holding)

      conn = get(conn, "/wallet-bench/#{tests.passed.id}/#{unquote(path)}")
      page = html_response(conn, 503)
      assert page =~ "Try again in a minute."
      # The busy page is the whole page, never drawn inside the site's own.
      assert length(String.split(page, "<!DOCTYPE html>")) == 2
      assert get_resp_header(conn, "retry-after") == ["30"]

      for holder <- holders, do: send(holder, :done)
    end

    # A store too slow to answer crashed the single file (Sentinel, 23 Oct): the
    # visitor is asked to try again, and the download place is given back.
    test "when the store does not answer in time, #{what} asks the visitor to try again", %{
      conn: conn,
      tests: tests
    } do
      Req.Test.stub(Evidence, &Req.Test.transport_error(&1, :timeout))

      conn = get(conn, "/wallet-bench/#{tests.passed.id}/#{unquote(path)}")
      assert html_response(conn, 503) =~ "Try again in a minute."
      assert get_resp_header(conn, "retry-after") == ["30"]
      assert Registry.count_match(TechtreeWeb.ResultsDownloads, :download, :_) == 0
    end

    test "#{what} gives its download place back when it ends", %{
      conn: conn,
      tests: tests,
      files: files
    } do
      store(files)

      for _download <- 1..6 do
        assert build_conn()
               |> get("/wallet-bench/#{tests.passed.id}/#{unquote(path)}")
               |> response(200)
      end

      assert Registry.count_match(TechtreeWeb.ResultsDownloads, :download, :_) == 0
      _ = conn
    end
  end

  # A picture a tested agent saved went out unchecked for secrets (security
  # assessment of 19 Oct, finding 1). One already on record is sent as plain
  # text, so it never shows as a picture.
  test "a recorded picture is sent as plain text", %{conn: conn, tests: tests, files: files} do
    png = <<0x89, "PNG\r\n", 0x1A, "\n", 0, 0, 0, 13, "IHDR", 0, 0, 0, 1, 0, 0, 0, 1>>
    sha256 = Base.encode16(:crypto.hash(:sha256, png), case: :lower)

    Techtree.Repo.query!(
      """
      UPDATE wallet_bench_turns
      SET evidence = evidence || jsonb_build_object('image-0.png', jsonb_build_object('bytes', $2::int, 'sha256', $3::text))
      WHERE attempt_id = $1 AND test = 'T1a'
      """,
      [Ecto.UUID.dump!(tests.passed.id), byte_size(png), sha256]
    )

    store(Map.put(files, Evidence.turn_key(tests.passed.id, "T1a", "image-0.png"), png))
    conn = get(conn, "/wallet-bench/#{tests.passed.id}/evidence/T1a/image-0.png")

    assert response(conn, 200) == png
    assert get_resp_header(conn, "content-type") == ["text/plain; charset=utf-8"]
  end

  # results.json names every field it carries, at every level; whatever else the
  # bench keeps on a test stays out of the download.
  test "only the named fields reach results.json", %{conn: conn, tests: tests, files: files} do
    Techtree.Repo.query!(
      """
      UPDATE wallet_bench_turns
      SET judgment = judgment || '{"kept_only_here": "unlisted-ruling-field"}',
          checks = coalesce(checks, '{}') || '{"kept_only_here": {"value": "unlisted-check-field"}}',
          evidence = jsonb_set(evidence, '{install.log,kept_only_here}', '"unlisted-file-field"')
      WHERE attempt_id = $1 AND test = 'T1a'
      """,
      [Ecto.UUID.dump!(tests.passed.id)]
    )

    Ash.Seed.seed!(Techtree.WalletBench.Payment, %{
      attempt_id: tests.passed.id,
      token: :usdc,
      amount: 20_000,
      state: :confirmed,
      from: "0x" <> String.duplicate("1", 40),
      to: "0x" <> String.duplicate("2", 40),
      nonce: 0,
      raw: "0x02unlisted-raw-field",
      hash: "0x" <> String.duplicate("3", 64),
      block: 1
    })

    store(files)
    zip = conn |> get(~p"/wallet-bench/#{tests.passed.id}/results.zip") |> response(200)
    {:ok, entries} = :zip.unzip(zip, [:memory])

    {_name, results} =
      Enum.find(entries, fn {name, _} -> List.to_string(name) =~ "results.json" end)

    refute results =~ "unlisted"
    results = Jason.decode!(results)
    keys = fn map -> map |> Map.keys() |> Enum.sort() end

    assert keys.(results) ==
             ~w(agent agent_address failure funding judge_cost_usd machine model_cost_usd page started_at status tests wallet_tool)

    assert [install | _] = results["tests"]

    assert keys.(install) ==
             ~w(base_check ended_at failure files folder judge_cost_usd model_cost_usd prompt ruling seconds started_at state test version_installed)

    assert keys.(install["ruling"]) == ~w(checks judged_by outcome reasoning summary)
    assert Enum.all?(install["ruling"]["checks"], &(keys.(&1) == ~w(answer check why)))
    assert Enum.all?(Map.values(install["files"]), &(keys.(&1) == ~w(bytes sha256)))
    assert [funding] = results["funding"]
    assert keys.(funding) == ~w(sent state transaction)
    assert install["version_installed"] == "0.3.45, the release this run asked for."
  end

  test "a test with no recorded files is its results alone", %{conn: conn, tests: tests} do
    {:ok, entries} =
      conn
      |> get(~p"/wallet-bench/#{tests.running.id}/results.zip")
      |> response(200)
      |> :zip.unzip([:memory])

    assert [{name, _results}] = entries
    assert List.to_string(name) =~ "results.json"
  end
end
