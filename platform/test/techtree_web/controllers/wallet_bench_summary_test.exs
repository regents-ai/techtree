defmodule TechtreeWeb.WalletBenchSummaryTest do
  @moduledoc """
  One wallet test's record as JSON at `/wallet-bench/:id/results.json`: the
  same record its zip starts with, for an agent that reads the test without its
  files, and a JSON 404 for an id that names no test.
  """

  use TechtreeWeb.ConnCase, async: false

  alias Techtree.WalletBenchFixture

  setup do
    %{tests: WalletBenchFixture.seed!()}
  end

  test "a test's record: its page, agent, wallet tool and each step with its files", %{
    conn: conn,
    tests: tests
  } do
    conn = get(conn, ~p"/wallet-bench/#{tests.passed.id}/results.json")

    assert get_resp_header(conn, "cache-control") == ["public, max-age=30"]
    body = json_response(conn, 200)

    assert body["page"] =~ "/wallet-bench/#{tests.passed.id}"
    assert is_binary(body["agent"]) and is_binary(body["wallet_tool"])
    assert [_ | _] = body["tests"]

    files = Map.new(WalletBenchFixture.files(%{passed: tests.passed}))

    listed =
      for step <- body["tests"],
          {file, %{"bytes" => bytes, "sha256" => sha256}} <- step["files"],
          do: {file, bytes, sha256}

    assert length(listed) == map_size(files)

    for {_key, recorded} <- files do
      sha256 = Base.encode16(:crypto.hash(:sha256, recorded), case: :lower)

      assert Enum.any?(listed, fn {_file, bytes, sum} ->
               bytes == byte_size(recorded) and sum == sha256
             end)
    end
  end

  test "a test still running answers too", %{conn: conn, tests: tests} do
    body = json_response(get(conn, ~p"/wallet-bench/#{tests.running.id}/results.json"), 200)
    assert body["page"] =~ tests.running.id
  end

  test "an id that names no test is a JSON 404 that says where ids come from", %{conn: conn} do
    for id <- [Ecto.UUID.generate(), "not-an-id"] do
      conn = get(conn, "/wallet-bench/#{id}/results.json")

      assert %{"error" => %{"code" => "wallet_test_not_found", "hint" => hint}} =
               json_response(conn, 404)

      assert hint =~ "/wallet-bench.json"
    end
  end
end
