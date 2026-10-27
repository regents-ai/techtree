defmodule Techtree.Agents.AgentTest do
  use Techtree.DataCase, async: true
  use ExUnitProperties

  alias Techtree.Actors
  alias Techtree.Agents

  @system %Actors.System{}

  property "a wallet's first World ID person stays its person, with that person's latest count" do
    # Each signed request's answer names nobody (nil) or one of three people.
    answer = one_of([constant(nil), tuple({member_of(~w(a b c)), integer(1..9)})])

    check all(answers <- list_of(answer, max_length: 8), max_runs: 40) do
      {:ok, agent} = Agents.sign_in_agent(wallet(), actor: @system)

      saved =
        Enum.reduce(answers, agent, fn
          nil, agent ->
            agent

          {person, count}, agent ->
            Agents.record_backing!(agent, human_id(person), count, actor: @system)
        end)

      case for {person, count} <- answers, do: {human_id(person), count} do
        [] ->
          assert {saved.world_id_human_id, saved.world_id_agent_count} == {nil, nil}

        [{first, _count} | _rest] = named ->
          {^first, latest} = named |> Enum.filter(&(elem(&1, 0) == first)) |> List.last()

          assert {saved.world_id_human_id, saved.world_id_agent_count} == {first, latest}

          assert Ash.get!(Agents.Agent, agent.id)
                 |> Map.take([:world_id_human_id, :world_id_agent_count]) ==
                   %{world_id_human_id: first, world_id_agent_count: latest}
      end
    end
  end

  test "one wallet is one agent, however often it signs in" do
    wallet = wallet()

    {:ok, first} = Agents.sign_in_agent(wallet, actor: @system)
    {:ok, again} = Agents.sign_in_agent(wallet, actor: @system)
    {:ok, other} = Agents.sign_in_agent(wallet(), actor: @system)

    assert again.id == first.id
    assert DateTime.compare(again.last_seen_at, first.last_seen_at) == :gt
    assert other.id != first.id
  end

  test "only the site itself adds an agent or names its World ID person" do
    {:ok, agent} = Agents.sign_in_agent(wallet(), actor: @system)
    refused = wallet()

    for actor <- [nil, Actors.Agent.for_agent(agent)] do
      assert {:error, %Ash.Error.Forbidden{}} = Agents.sign_in_agent(refused, actor: actor)

      assert {:error, %Ash.Error.Forbidden{}} =
               Agents.record_backing(agent, human_id("a"), 1, actor: actor)
    end

    refute Enum.any?(Ash.read!(Agents.Agent), &(&1.wallet_address == refused))
    assert %{world_id_human_id: nil} = Ash.get!(Agents.Agent, agent.id)
  end

  defp wallet, do: "0x" <> Base.encode16(:crypto.strong_rand_bytes(20), case: :lower)

  defp human_id(person),
    do: "0x" <> Base.encode16(:crypto.hash(:sha256, person), case: :lower)
end
