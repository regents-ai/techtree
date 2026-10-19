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

  # A stored file that no longer matches its recorded sha256 is never handed out:
  # the download stops at that file, before any of its bytes are sent.
  test "a stored file changed since it was recorded stops the download", %{
    conn: conn,
    tests: tests,
    files: files
  } do
    key = Evidence.turn_key(tests.passed.id, "T2", "session.jsonl")
    store(Map.update!(files, key, &(&1 <> "changed")))

    assert_raise RuntimeError, ~r/does not match the sha256 recorded with it/, fn ->
      get(conn, ~p"/wallet-bench/#{tests.passed.id}/results.zip")
    end
  end

  # results.json names every field it carries; whatever else the bench keeps on
  # a test's ruling or checks stays out of the download.
  test "only the named fields reach results.json", %{conn: conn, tests: tests, files: files} do
    Techtree.Repo.query!(
      """
      UPDATE wallet_bench_turns
      SET judgment = judgment || '{"kept_only_here": "unlisted-ruling-field"}',
          checks = coalesce(checks, '{}') || '{"kept_only_here": {"value": "unlisted-check-field"}}'
      WHERE attempt_id = $1
      """,
      [Ecto.UUID.dump!(tests.passed.id)]
    )

    store(files)
    zip = conn |> get(~p"/wallet-bench/#{tests.passed.id}/results.zip") |> response(200)
    {:ok, entries} = :zip.unzip(zip, [:memory])

    {_name, results} =
      Enum.find(entries, fn {name, _} -> List.to_string(name) =~ "results.json" end)

    refute results =~ "unlisted"

    assert %{"tests" => [install | _]} = Jason.decode!(results)

    assert Map.keys(install) |> Enum.sort() ==
             ~w(base_check ended_at failure files folder judge_cost_usd model_cost_usd prompt ruling seconds started_at state test version_installed)

    assert Map.keys(install["ruling"]) |> Enum.sort() ==
             ~w(checks judged_by outcome reasoning summary)

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
