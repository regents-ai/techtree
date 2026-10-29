defmodule Techtree.WalletBench.BatchTest do
  # A pair batch, with and without a Skill: the manifest names the Skill and the
  # sha256 of its SKILL.md and each attempt's model budget; starting it freezes
  # both in every attempt; and the attempt's first step puts the Skill on the
  # machine, checks it read back the same and starts the translator with that
  # budget, before any model is called.
  use Techtree.DataCase, async: false
  use Oban.Testing, repo: Techtree.Repo

  require Ash.Query

  alias Techtree.WalletBench
  alias Techtree.WalletBench.{Attempt, Batch, Catalog, Turn}

  @skill_md File.read!(Path.expand("../../../../skills/wallet-secrets/SKILL.md", __DIR__))
  @sha256 :crypto.hash(:sha256, @skill_md) |> Base.encode16(case: :lower)

  defp plan(extra \\ []) do
    Batch.plan([axis: "pair", id: "H05-W01", operator: "test-operator", repeats: 3] ++ extra)
  end

  defp refused(manifest, reason) do
    assert_raise ArgumentError, "Invalid wallet-bench plan: " <> reason, fn ->
      Batch.validate!(manifest)
    end
  end

  test "a pair plans one agent and one wallet tool at their default releases, with the Skill named" do
    manifest = plan(skill: "wallet-secrets", model_budget_usd: 1.0)

    assert manifest["harnesses"] == %{"H05" => Catalog.harness_pin!("H05")}
    assert manifest["wallets"] == %{"W01" => Catalog.wallet_version!("W01")}
    assert manifest["skill"] == %{"name" => "wallet-secrets", "sha256" => @sha256}
    assert Catalog.skill!("wallet-secrets").body == @skill_md

    assert %{attempts: 3, model_budget_usd: 1.0, model_cap_usd: 3.0, skill: %{"name" => _}} =
             Batch.summary(manifest)

    # The same pair without the Skill keeps the bench's own budget.
    plain = plan()
    assert plain["skill"] == nil
    assert %{attempts: 3, model_cap_usd: 15} = Batch.summary(plain)
  end

  test "a plan with a changed or unknown Skill, a budget out of range or another agent is refused" do
    manifest = plan(skill: "wallet-secrets")

    refused(
      put_in(manifest, ["skill", "sha256"], String.duplicate("0", 64)),
      "Skill unknown or changed; make a new plan"
    )

    refused(
      put_in(manifest, ["skill", "name"], "techtree"),
      "Skill unknown or changed; make a new plan"
    )

    for budget <- [0, -1, 5.01, "1"] do
      refused(
        Map.put(manifest, "model_budget_usd", budget),
        "model budget (above 0, at most 5 dollars an attempt)"
      )
    end

    hermes = Batch.plan(axis: "pair", id: "H04-W01", operator: "test-operator")

    refused(
      Map.put(hermes, "skill", manifest["skill"]),
      "a Skill reaches only the agents in Catalog.skill_harness_ids/0"
    )

    assert_raise ArgumentError, "a pair runs both default releases", fn ->
      plan(version: "0.3.45")
    end

    assert_raise ArgumentError,
                 "Invalid wallet-bench plan: a harness that takes the wallet test",
                 fn ->
                   Batch.plan(axis: "pair", id: "H06-W01", operator: "test-operator")
                 end
  end

  describe "a started Skill batch" do
    setup do
      previous = Application.get_env(:regent_sprites, :req_options)
      bench = Application.fetch_env!(:techtree, Techtree.WalletBench)
      Application.put_env(:regent_sprites, :token, "test-sprites-token")
      Application.put_env(:regent_sprites, :req_options, plug: {Req.Test, __MODULE__})

      Application.put_env(
        :techtree,
        Techtree.WalletBench,
        Keyword.put(bench, :model_key, "test-key")
      )

      Req.Test.stub(__MODULE__, &sprites/1)

      on_exit(fn ->
        Application.delete_env(:regent_sprites, :token)
        Application.put_env(:techtree, Techtree.WalletBench, bench)

        if previous,
          do: Application.put_env(:regent_sprites, :req_options, previous),
          else: Application.delete_env(:regent_sprites, :req_options)
      end)

      manifest = plan(skill: "wallet-secrets", model_budget_usd: 1.0)
      {:ok, attempts} = Batch.start(manifest)
      %{manifest: manifest, attempts: attempts}
    end

    test "every attempt keeps the Skill and budget, and its first step installs the Skill and the budget",
         %{manifest: manifest, attempts: attempts} do
      assert length(attempts) == 3

      for attempt <- attempts do
        assert attempt.run_spec["skill"] == %{"name" => "wallet-secrets", "sha256" => @sha256}
        assert attempt.run_spec["model_budget_usd"] == 1.0
      end

      [machine] =
        Techtree.WalletBench.Machine
        |> Ash.Query.filter(batch_id == ^manifest["batch"])
        |> Ash.read!(authorize?: false)

      attempt =
        attempts
        |> hd()
        |> Ash.Seed.update!(%{state: :leased, machine_id: machine.id})
        |> Ash.Changeset.for_update(:attach_credentials, %{})
        |> Ash.update!(authorize?: false)

      assert attempt.state == :testing
      assert Process.get(:skill_md) == @skill_md
      assert Process.get(:model_key) == "test-key"

      # The Skill goes on before the key, and the translator gets the batch's budget.
      assert Process.get(:calls) == [
               ["bash", "/work/bin/machine/skill.sh", "wallet-secrets"],
               ["bash", "/work/bin/machine/credentials.sh", "attach", "1.0"]
             ]

      event = attempt.id |> WalletBench.list_attempt_events!() |> List.last()

      assert event.detail == %{
               "credentials" => "attached",
               "model_budget_usd" => 1.0,
               "skill" => %{"name" => "wallet-secrets", "sha256" => @sha256}
             }

      # The first prompt is the one every attempt gets; the Skill changes no word of it.
      [turn] = Ash.read!(Turn, authorize?: false) |> Enum.filter(&(&1.attempt_id == attempt.id))
      assert turn.test == :T1a
      assert turn.prompt == Catalog.attempt_prompt(attempt, :T1a)
      refute turn.prompt =~ "wallet-secrets"
      refute turn.prompt =~ "Skill"
    end

    test "a Skill that reads back differently on the machine stops the step before the key goes on",
         %{manifest: manifest, attempts: attempts} do
      Process.put(:read_back, String.duplicate("0", 64) <> "\n")

      [machine] =
        Techtree.WalletBench.Machine
        |> Ash.Query.filter(batch_id == ^manifest["batch"])
        |> Ash.read!(authorize?: false)

      assert {:error, error} =
               attempts
               |> hd()
               |> Ash.Seed.update!(%{state: :leased, machine_id: machine.id})
               |> Ash.Changeset.for_update(:attach_credentials, %{})
               |> Ash.update(authorize?: false)

      assert Exception.message(error) =~
               "The Skill on the machine is not the one the batch names."

      assert Process.get(:calls) == [["bash", "/work/bin/machine/skill.sh", "wallet-secrets"]]
      assert Ash.get!(Attempt, hd(attempts).id, authorize?: false).state == :leased
    end

    test "status adds up what the batch's model and judge calls have cost so far",
         %{manifest: manifest, attempts: [first | _rest]} do
      Ash.Seed.seed!(Turn, %{
        attempt_id: first.id,
        test: :T1a,
        state: :judged,
        prompt: "Install the wallet tool.",
        model_spend_usd: Decimal.new("0.1055"),
        judge_cost_usd: Decimal.new("0.0970")
      })

      status = Batch.status(manifest["batch"])
      assert Decimal.equal?(status.model_spend_usd, "0.1055")
      assert Decimal.equal?(status.judge_cost_usd, "0.0970")
      assert length(status.attempts) == 3
      assert Enum.count(status.attempts, &(&1.model_spend_usd == nil)) == 2
    end
  end

  # The Sprites exec API, enough for the attempt's first step.
  defp sprites(%{method: "POST", request_path: "/v1/sprites/" <> rest} = conn) do
    true = String.ends_with?(rest, "/exec")
    argv = for {"cmd", value} <- URI.query_decoder(conn.query_string), do: value
    {:ok, stdin, conn} = Plug.Conn.read_body(conn)
    Process.put(:calls, (Process.get(:calls) || []) ++ [argv])

    case argv do
      ["bash", "/work/bin/machine/skill.sh", "wallet-secrets"] ->
        Process.put(:skill_md, stdin)
        sha256 = :crypto.hash(:sha256, stdin) |> Base.encode16(case: :lower)
        frames(conn, Process.get(:read_back) || sha256 <> "\n")

      ["bash", "/work/bin/machine/credentials.sh", "attach", _budget] ->
        Process.put(:model_key, stdin)
        frames(conn, "attached\n")
    end
  end

  defp frames(conn, stdout), do: Plug.Conn.send_resp(conn, 200, <<1>> <> stdout <> <<3, 0>>)
end
