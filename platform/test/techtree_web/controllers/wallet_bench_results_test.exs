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

    assert [%{"folder" => "T1a", "ruling" => %{"outcome" => "PASS"}}, %{"folder" => "T2"}] =
             results["tests"]

    for {key, body} <- files, String.contains?(key, tests.passed.id) do
      [_attempts, _id, turn, file] = String.split(key, "/")
      assert entries["#{folder}/#{turn}/#{file}"] == body
    end

    assert map_size(entries) == 1 + Enum.count(files, fn {key, _} -> key =~ tests.passed.id end)
  end

  # A stored file that no longer matches its recorded sha256 is never handed out.
  test "a stored file changed since it was recorded stops the download", %{
    conn: conn,
    tests: tests,
    files: files
  } do
    key = Evidence.turn_key(tests.passed.id, "T2", "session.jsonl")
    store(Map.update!(files, key, &(&1 <> "changed")))

    assert_error_sent 500, fn -> get(conn, ~p"/wallet-bench/#{tests.passed.id}/results.zip") end
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
