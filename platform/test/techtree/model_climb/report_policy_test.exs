defmodule Techtree.ModelClimb.ReportPolicyTest do
  @moduledoc """
  Who may keep and read a Model Climb report, asked of the resource itself with
  the actors `TechtreeWeb.Plugs.AgentWallet` makes: an agent acting as its
  person, and an agent acting only as itself.
  """

  use Techtree.DataCase, async: true

  alias Techtree.Actors.Agent
  alias Techtree.ModelClimb
  alias Techtree.ModelClimb.Report

  test "only an agent acting as its person may keep a report" do
    assert Ash.can?({Report, :submit}, paired("did:privy:owner"))
    refute Ash.can?({Report, :submit}, Agent.for_agent(agent()))
    refute Ash.can?({Report, :submit}, Agent.for_agent(agent(), :person_not_here))
  end

  test "a report is read only by its owner's agents" do
    report = seed_report("did:privy:owner")

    assert [%{id: id}] = ModelClimb.list_my_reports!(actor: paired("did:privy:owner"))
    assert id == report.id

    assert {:ok, %{id: ^id}} =
             ModelClimb.get_my_report(report.report_digest, actor: paired("did:privy:owner"))

    for actor <- [
          paired("did:privy:someone-else"),
          Agent.for_agent(agent()),
          Agent.for_agent(agent(), :person_not_here)
        ] do
      assert ModelClimb.list_my_reports!(actor: actor) == []
      assert {:ok, nil} = ModelClimb.get_my_report(report.report_digest, actor: actor)
    end
  end

  defp paired(owner) do
    account = %{
      id: System.unique_integer([:positive]),
      display_name: nil,
      wallet_address: wallet()
    }

    Agent.paired(agent(), account, %{id: Ecto.UUID.generate(), privy_user_id: owner})
  end

  defp agent, do: %{id: Ecto.UUID.generate(), wallet_address: wallet()}

  defp seed_report(owner) do
    digest = "sha256:" <> Base.encode16(:crypto.strong_rand_bytes(32), case: :lower)

    Ash.Seed.seed!(Report, %{
      owner_privy_user_id: owner,
      pairing_id: Ecto.UUID.generate(),
      acting_agent_wallet: wallet(),
      idempotency_key: "key-1",
      request_digest: digest,
      report_digest: digest,
      signer_key_id: "key",
      results: %{},
      paired_outcomes: %{},
      proof: "{}"
    })
  end

  defp wallet, do: "0x" <> Base.encode16(:crypto.strong_rand_bytes(20), case: :lower)
end
