defmodule Techtree.Messages.LeaveTest do
  # Leaving a message for Techtree's team, through the actions every surface calls:
  # - a signed-in person, an agent no person paired and a paired agent each leave
  #   one, recorded as themselves, and get its receipt;
  # - who left it comes from the actor alone: no input can name a sender;
  # - the topic, the text and reply_to are bounded, and nothing is kept when refused;
  # - an operation_id answers its first message again, and refuses any other use,
  #   also when another call kept it between this call's read and its write;
  # - each sender leaves 10 an hour, and each address 30;
  # - only the site's admins read messages.
  use ExUnit.Case, async: false

  alias Techtree.{Accounts, Agents, Messages, Repo}
  alias Techtree.Actors.{Agent, Human, System}
  alias Techtree.Messages.{Message, Refused}

  setup do
    :ok = Ecto.Adapters.SQL.Sandbox.checkout(Repo)
    %{key: Ecto.UUID.generate()}
  end

  test "a person, an agent and a paired agent each leave a message as themselves", %{key: key} do
    {person, account} = person()

    assert {:ok, %Message{} = left} =
             Messages.leave_message(
               %{topic: "watchdog", body: "Hello team", reply_to: "me@example.com"},
               actor: person,
               context: %{client_key: key}
             )

    assert Message.receipt(left) ==
             %{id: left.id, topic: "watchdog", inserted_at: left.inserted_at}

    assert %{human_account_id: id, agent_id: nil, sender_name: name, operation_id: nil} =
             stored(left.id)

    assert {id, name} == {account.id, person.name}

    agent = agent()

    assert {:ok, %{replayed: false, receipt: %{id: id, topic: "watchdog"}}} =
             leave(agent, "watchdog", %{body: "From an agent"}, key)

    assert %{human_account_id: nil, agent_id: agent_id, reply_to: nil} = stored(id)
    assert agent_id == agent.agent_id

    {paired, account} = paired_agent()
    assert {:ok, %{receipt: %{id: id}}} = leave(paired, "watchdog", %{body: "For my person"}, key)
    assert %{human_account_id: human, agent_id: agent_id} = stored(id)
    assert {human, agent_id} == {account.id, paired.agent_id}
  end

  test "no input names the sender or the operation, so a message is never left as anyone else",
       %{key: key} do
    {person, _account} = person()
    {_other, other} = person()
    count = count()

    for input <- [
          %{human_account_id: other.id, sender_name: "Other"},
          %{agent_id: Ecto.UUID.generate()},
          %{operation_id: Ecto.UUID.generate()}
        ] do
      assert {:error, %Ash.Error.Invalid{}} =
               Messages.leave_message(
                 Map.merge(%{topic: "watchdog", body: "Hi"}, input),
                 actor: person,
                 context: %{client_key: key}
               )
    end

    assert {:error, %Ash.Error.Invalid{}} =
             leave(agent(), "watchdog", %{body: "Hi", agent_id: Ecto.UUID.generate()}, key)

    assert count() == count
  end

  test "the topic, the text and reply_to are bounded, and a refusal keeps nothing", %{key: key} do
    agent = agent()
    count = count()

    for {topic, input} <- [
          {"watchdog", %{body: String.duplicate("a", 2001)}},
          {"watchdog", %{body: ""}},
          {"watchdog", %{body: "Hi", reply_to: String.duplicate("a", 201)}},
          {"Watchdog!", %{body: "Hi"}},
          {String.duplicate("a", 41), %{body: "Hi"}}
        ] do
      assert {:error, %Ash.Error.Invalid{}} = leave(agent, topic, input, key)
    end

    assert {:ok, _} = leave(agent, "watchdog", %{body: String.duplicate("a", 2000)}, key)
    assert count() == count + 1
  end

  test "an operation_id answers its first message again and refuses any other use", %{key: key} do
    agent = agent()
    input = %{body: "Once", reply_to: "a room", operation_id: Ecto.UUID.generate()}

    again = fn topic, input ->
      Messages.agent_leave_message(topic, input, actor: agent, context: %{client_key: key})
    end

    assert {:ok, %{replayed: false, receipt: receipt}} = again.("watchdog", input)
    assert {:ok, %{replayed: true, receipt: ^receipt}} = again.("watchdog", input)

    for {topic, changed} <- [
          {"watchdog", %{input | body: "Twice"}},
          {"watchdog", %{input | reply_to: "elsewhere"}},
          {"verify", input}
        ] do
      assert {:error, %{errors: [%Refused{code: "idempotency_conflict"}]}} =
               again.(topic, changed)
    end

    # Another agent's use of the same UUID is its own message.
    assert {:ok, %{replayed: false}} = leave(agent(), "watchdog", input, key)
    assert count_by(agent) == 1
  end

  test "a retry never uses an allowance" do
    agent = agent()
    input = %{body: "Once", operation_id: Ecto.UUID.generate()}

    for _ <- 1..12 do
      assert {:ok, _} = leave(agent, "watchdog", input, Ecto.UUID.generate())
    end

    assert count_by(agent) == 1
  end

  test "an operation_id another call keeps first answers that call's message", %{key: key} do
    agent = agent()
    input = %{body: "Once", operation_id: Ecto.UUID.generate()}
    handler = "message-kept-first-#{:erlang.unique_integer([:positive])}"

    # The other call commits just after this one has read that the key is free.
    :ok =
      :telemetry.attach(
        handler,
        [:techtree, :repo, :query],
        fn
          _event, _measurements, %{source: "left_messages"}, _config ->
            :telemetry.detach(handler)

            Ash.Seed.seed!(Message, %{
              topic: "watchdog",
              body: input.body,
              sender_name: agent.name,
              agent_id: agent.agent_id,
              operation_id: input.operation_id
            })

          _event, _measurements, _metadata, _config ->
            :ok
        end,
        nil
      )

    on_exit(fn -> :telemetry.detach(handler) end)

    assert {:ok, %{replayed: true, receipt: %{id: id}}} = leave(agent, "watchdog", input, key)
    assert [%{id: ^id}] = by(agent)
  end

  test "each sender leaves 10 messages an hour, then is refused until it passes" do
    agent = agent()

    for n <- 1..10 do
      assert {:ok, _} = leave(agent, "watchdog", %{body: "Message #{n}"}, Ecto.UUID.generate())
    end

    assert {:error, %Ash.Error.Invalid{errors: [%{field: :body}]}} =
             leave(agent, "watchdog", %{body: "One more"}, Ecto.UUID.generate())

    assert count_by(agent) == 10

    {person, _account} = person()

    assert {:ok, _} =
             Messages.leave_message(%{topic: "watchdog", body: "Still free"},
               actor: person,
               context: %{client_key: Ecto.UUID.generate()}
             )
  end

  test "each address leaves 30 messages an hour, whoever sends them", %{key: key} do
    for n <- 1..30 do
      assert {:ok, _} = leave(agent(), "watchdog", %{body: "Message #{n}"}, key)
    end

    late = agent()

    assert {:error, %Ash.Error.Invalid{errors: [%{field: :body}]}} =
             leave(late, "watchdog", %{body: "One more"}, key)

    assert count_by(late) == 0
    assert {:ok, _} = leave(late, "watchdog", %{body: "From elsewhere"}, Ecto.UUID.generate())
  end

  test "only the site's admins read messages", %{key: key} do
    {person, _account} = person()
    agent = agent()
    operation = Ecto.UUID.generate()
    {:ok, _} = leave(agent, "watchdog", %{body: "Private", operation_id: operation}, key)
    did = "did:privy:admin-" <> Ecto.UUID.generate()
    put_admins([did])

    admin = %RegentAgents.Person{privy_user_id: did, role: :admin}
    assert %{results: [%{body: "Private"} | _]} = Messages.list_messages!(actor: admin)

    for reader <- [
          person,
          agent,
          %RegentAgents.Person{privy_user_id: did},
          %RegentAgents.Person{privy_user_id: "did:privy:not-listed", role: :admin},
          nil
        ] do
      assert {:error, %Ash.Error.Forbidden{}} = Messages.list_messages(actor: reader)

      assert {:error, %Ash.Error.Forbidden{}} =
               Messages.get_agent_message(agent.agent_id, operation, actor: reader)
    end
  end

  defp leave(agent, topic, input, key) do
    Messages.agent_leave_message(
      topic,
      Map.put_new(input, :operation_id, Ecto.UUID.generate()),
      actor: agent,
      context: %{client_key: key}
    )
  end

  defp stored(id), do: Ash.get!(Message, id, authorize?: false)
  defp count, do: Message |> Ash.read!(authorize?: false) |> length()
  defp count_by(agent), do: length(by(agent))

  defp by(agent),
    do: Message |> Ash.read!(authorize?: false) |> Enum.filter(&(&1.agent_id == agent.agent_id))

  defp put_admins(admins) do
    old = Application.fetch_env(:regent_agents, :admins)
    Application.put_env(:regent_agents, :admins, admins)

    on_exit(fn ->
      case old do
        {:ok, admins} -> Application.put_env(:regent_agents, :admins, admins)
        :error -> Application.delete_env(:regent_agents, :admins)
      end
    end)
  end

  defp person do
    did = "did:privy:message-" <> Ecto.UUID.generate()
    wallet = wallet()
    account = Accounts.register_verified!(did, wallet, [wallet], actor: %System{})
    {Human.for_account(account), account}
  end

  defp agent, do: Agent.for_agent(Agents.sign_in_agent!(wallet(), actor: %System{}))

  defp paired_agent do
    did = "did:privy:message-" <> Ecto.UUID.generate()
    person_wallet = wallet()
    agent_wallet = wallet()
    account = Accounts.register_verified!(did, person_wallet, [person_wallet], actor: %System{})
    code = RegentAgents.issue_pairing_code!(actor: %RegentAgents.Person{privy_user_id: did})

    pairing =
      RegentAgents.pair_agent!(code.code, "Agent", :codex,
        actor: %RegentAgents.Agent{wallet: agent_wallet}
      )

    record = Agents.sign_in_agent!(agent_wallet, actor: %System{})
    {Agent.paired(record, account, pairing), account}
  end

  defp wallet, do: "0x" <> Base.encode16(:crypto.strong_rand_bytes(20), case: :lower)
end
