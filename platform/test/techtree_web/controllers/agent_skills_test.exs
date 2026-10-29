defmodule TechtreeWeb.AgentSkillsTest do
  @moduledoc """
  The Techtree skill as agents fetch it: `/skill.md`, the skills index (with the
  wallet-secrets skill beside it) with a zip whose digest is the one listed and
  each file on its own, and each agent's
  own skill at `/agents/SLUG/skill.md`. Also the browser tools that read a
  Result's bundle, a Skill and the Wallet Bench, as `/capabilities.json` lists them.
  """

  use TechtreeWeb.ConnCase, async: true

  @skill_md File.read!(Path.expand("../../../../skills/techtree/SKILL.md", __DIR__))
  @routes Enum.map(
            TechtreeWeb.Router.__routes__(),
            &"#{String.upcase(to_string(&1.verb))} #{&1.path}"
          )

  defp content_type(conn), do: conn |> get_resp_header("content-type") |> List.first()

  test "/skill.md is the Techtree skill's SKILL.md, byte for byte", %{conn: conn} do
    conn = get(conn, ~p"/skill.md")

    assert conn.status == 200
    assert content_type(conn) =~ "text/markdown"
    assert conn.resp_body == @skill_md
  end

  test "the skills index lists the Techtree and wallet-secrets skills with the digest of each zip",
       %{conn: conn} do
    index = get(conn, "/.well-known/agent-skills/index.json")

    assert index.status == 200
    assert content_type(index) =~ "application/json"
    assert get_resp_header(index, "access-control-allow-origin") == ["*"]

    assert %{"$schema" => _schema, "skills" => skills} = Jason.decode!(index.resp_body)
    assert Enum.map(skills, & &1["name"]) == ["techtree", "wallet-secrets"]

    for skill <- skills do
      name = skill["name"]
      skill_md = File.read!(Path.expand("../../../../skills/#{name}/SKILL.md", __DIR__))
      assert %{"type" => "archive", "url" => url, "digest" => digest} = skill
      assert skill["description"] != ""

      zip = get(build_conn(), url)

      assert zip.status == 200
      assert content_type(zip) == "application/zip"

      assert digest ==
               "sha256:" <> Base.encode16(:crypto.hash(:sha256, zip.resp_body), case: :lower)

      {:ok, files} = :zip.unzip(zip.resp_body, [:memory])
      assert {~c"SKILL.md", skill_md} in files

      for {file, body} <- files do
        single = get(build_conn(), "/.well-known/agent-skills/#{name}/#{file}")
        assert single.status == 200, "#{name}/#{file} answered #{single.status}"
        assert single.resp_body == body
      end
    end
  end

  test "the same zip is served every time", %{conn: conn} do
    first = get(conn, "/.well-known/agent-skills/techtree.zip")

    assert get(build_conn(), "/.well-known/agent-skills/techtree.zip").resp_body ==
             first.resp_body
  end

  test "a path the index does not serve is a 404", %{conn: conn} do
    for path <- ["nope.zip", "techtree/NOPE.md", "techtree/../mix.exs", "techtree"] do
      assert_error_sent 404, fn -> get(conn, "/.well-known/agent-skills/#{path}") end
    end
  end

  test "each agent the side panel offers has its own skill: the Techtree skill and its own set up",
       %{conn: conn} do
    for harness <- RegentAgents.Harness.featured() do
      slug = harness |> to_string() |> String.replace("_", "-")
      guide = get(build_conn(), "/agents/#{slug}/skill.md")

      assert guide.status == 200, "#{slug} answered #{guide.status}"
      assert content_type(guide) =~ "text/markdown"
      assert String.starts_with?(guide.resp_body, @skill_md)
      assert byte_size(guide.resp_body) > byte_size(@skill_md)
      refute guide.resp_body =~ "{{"
    end

    for slug <- ["nobody", "grok_bot"] do
      assert_error_sent 404, fn -> get(conn, "/agents/#{slug}/skill.md") end
    end
  end

  test "the browser tools for bundles, Skills and the Wallet Bench are listed as public reads",
       %{conn: conn} do
    tools =
      Map.new(json_response(get(conn, ~p"/capabilities.json"), 200)["tools"], &{&1["name"], &1})

    for name <- ~w(results_bundle skills_show wallet_bench_list wallet_bench_show) do
      assert %{"annotations" => %{"readOnlyHint" => true}} = tool = tools[name]
      assert tool["requires"] == "none"
      assert tool["state_changing"] == false
      assert tool["payment"] == "none"
      assert tool["interfaces"]["webmcp"] == name

      route = String.replace(tool["route"], ~r/\{([a-z_]+)\}/, ":\\1")
      assert route in @routes, "#{name} reads #{route}, which the site does not answer"
    end
  end
end
