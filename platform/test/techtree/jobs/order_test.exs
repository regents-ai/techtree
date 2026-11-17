defmodule Techtree.Jobs.OrderTest do
  # Job orders through the domain's actions, against a stand-in Base node:
  # - an agent asks, the team checks and quotes, and the quote gives the order
  #   its payment reference and the block its payments are read from;
  # - each move is allowed only from the states it starts from;
  # - who may ask, read, quote, refuse, cancel and look now;
  # - the payment read: what counts, when, from whom, and what an order becomes.
  use Techtree.DataCase, async: false
  use Oban.Testing, repo: Techtree.Repo

  alias Techtree.Jobs
  alias Techtree.Jobs.{Deposit, Order, Payment}
  alias Techtree.Actors.{Human, System}
  alias Techtree.{JobsFixture, NetworkFixture}
  alias Techtree.Jobs.Order.Workers.{LookNow, ReadPayment}

  @head 40_000_000
  @confirmations 300

  setup do
    admin_id = "did:privy:jobs-admin-" <> Ecto.UUID.generate()
    JobsFixture.put_admins([admin_id])
    JobsFixture.node(%{head: @head})

    %{
      admin: %RegentAgents.Person{privy_user_id: admin_id, role: :admin},
      agent: JobsFixture.agent()
    }
  end

  describe "asking and quoting" do
    test "an agent asks, the team checks and quotes, and the quote mints a reference",
         %{agent: agent, admin: admin} do
      order = JobsFixture.order(agent)

      assert order.state == :requested
      assert order.agent_id == agent.agent_id
      assert order.human_account_id == nil
      assert order.requested_at
      assert order.payment_reference == nil

      checking = Jobs.check_order!(order, actor: admin)
      assert checking.state == :checking
      assert checking.checking_at

      expires_at = DateTime.add(DateTime.utc_now(), 3, :day)

      quoted =
        Jobs.quote_order!(checking, 2_500_000, "The refund Skill.", expires_at, actor: admin)

      assert quoted.state == :quoted
      assert quoted.quoted_at
      assert {quoted.quote_amount, quoted.quote_scope} == {2_500_000, "The refund Skill."}
      assert quoted.quote_expires_at == expires_at
      assert quoted.payment_reference =~ ~r/\A0x[0-9a-f]{64}\z/
      assert quoted.next_block == @head

      other = JobsFixture.quoted(agent, admin, 2_500_000)
      refute other.payment_reference == quoted.payment_reference
    end

    test "a paired agent's order carries its person", %{admin: admin} do
      paired = NetworkFixture.paired_agent()
      order = JobsFixture.order(paired)

      assert order.human_account_id == paired.human_account_id

      person = %Human{human_account_id: paired.human_account_id}
      assert {:ok, %Order{}} = Jobs.get_order(order.id, actor: person)
      assert {:ok, %Order{}} = Jobs.get_order(order.id, actor: admin)
    end

    test "a quote needs its amount, scope and expiry, and an amount above nothing",
         %{agent: agent, admin: admin} do
      checking = agent |> JobsFixture.order() |> Jobs.check_order!(actor: admin)
      expires_at = DateTime.add(DateTime.utc_now(), 1, :day)

      assert {:error, %Ash.Error.Invalid{}} =
               Jobs.quote_order(checking, 0, "Scope", expires_at, actor: admin)

      assert {:error, %Ash.Error.Invalid{}} =
               Jobs.quote_order(checking, 1_000, nil, expires_at, actor: admin)

      assert {:error, %Ash.Error.Invalid{}} =
               Jobs.quote_order(checking, 1_000, "Scope", nil, actor: admin)

      assert Ash.reload!(checking, authorize?: false).state == :checking
    end

    test "a quote set while Base cannot be read is refused, and the order stays checking",
         %{agent: agent, admin: admin} do
      checking = agent |> JobsFixture.order() |> Jobs.check_order!(actor: admin)
      JobsFixture.node(%{down: true})

      assert {:error, %Ash.Error.Invalid{} = error} =
               Jobs.quote_order(checking, 1_000, "Scope", DateTime.utc_now(), actor: admin)

      assert Exception.message(error) =~ "Base could not be read"
      assert Ash.reload!(checking, authorize?: false).state == :checking
    end

    test "each move starts only from its own states", %{agent: agent, admin: admin} do
      order = JobsFixture.order(agent)
      expires_at = DateTime.add(DateTime.utc_now(), 1, :day)

      assert {:error, %Ash.Error.Invalid{}} =
               Jobs.quote_order(order, 1_000, "Scope", expires_at, actor: admin)

      assert Jobs.refuse_order!(order, actor: admin).state == :refused
      assert {:error, %Ash.Error.Invalid{}} = Jobs.check_order(order, actor: admin)
      assert {:error, %Ash.Error.Invalid{}} = Jobs.cancel_order(order, actor: agent)

      checking = agent |> JobsFixture.order() |> Jobs.check_order!(actor: admin)
      assert {:error, %Ash.Error.Invalid{}} = Jobs.check_order(checking, actor: admin)
      refused = Jobs.refuse_order!(checking, actor: admin)
      assert {refused.state, is_struct(refused.refused_at, DateTime)} == {:refused, true}

      quoted = JobsFixture.quoted(agent, admin, 1_000)
      assert {:error, %Ash.Error.Invalid{}} = Jobs.refuse_order(quoted, actor: admin)
      cancelled = Jobs.cancel_order!(quoted, actor: agent)
      assert {cancelled.state, is_struct(cancelled.cancelled_at, DateTime)} == {:cancelled, true}

      requested = JobsFixture.order(agent)
      assert Jobs.cancel_order!(requested, actor: agent).state == :cancelled
    end
  end

  describe "who may do what" do
    test "only a signed agent asks", %{admin: admin} do
      person = %Human{human_account_id: 1}

      for actor <- [person, admin, %System{}, nil] do
        assert {:error, %Ash.Error.Forbidden{}} =
                 Jobs.request_order(:evals, "Title", "Success", actor: actor)
      end
    end

    test "only the team checks, quotes and refuses", %{agent: agent, admin: admin} do
      order = JobsFixture.order(agent)
      checking = agent |> JobsFixture.order() |> Jobs.check_order!(actor: admin)
      expires_at = DateTime.add(DateTime.utc_now(), 1, :day)

      for actor <- [
            agent,
            JobsFixture.agent(),
            %Human{human_account_id: 1},
            %RegentAgents.Person{privy_user_id: admin.privy_user_id},
            %RegentAgents.Person{privy_user_id: "did:privy:not-listed", role: :admin},
            %System{},
            nil
          ] do
        assert {:error, %Ash.Error.Forbidden{}} = Jobs.check_order(order, actor: actor)
        assert {:error, %Ash.Error.Forbidden{}} = Jobs.refuse_order(order, actor: actor)

        assert {:error, %Ash.Error.Forbidden{}} =
                 Jobs.quote_order(checking, 1_000, "Scope", expires_at, actor: actor)
      end
    end

    test "the order and its quote are read by its agent, its person and the team only",
         %{admin: admin} do
      paired = NetworkFixture.paired_agent()
      quoted = JobsFixture.quoted(paired, admin, 1_000)

      for actor <- [paired, %Human{human_account_id: paired.human_account_id}, admin] do
        assert {:ok, %Order{quote_amount: 1_000, payment_reference: reference}} =
                 Jobs.get_order(quoted.id, actor: actor)

        assert reference == quoted.payment_reference
      end

      for actor <- [
            JobsFixture.agent(),
            NetworkFixture.paired_agent(),
            %Human{human_account_id: paired.human_account_id + 1},
            %System{},
            nil
          ] do
        assert {:error, %Ash.Error.Invalid{errors: [%Ash.Error.Query.NotFound{}]}} =
                 Jobs.get_order(quoted.id, actor: actor)
      end
    end

    test "its agent and its person cancel; nobody else does", %{admin: admin} do
      paired = NetworkFixture.paired_agent()
      order = JobsFixture.order(paired)

      for actor <- [
            JobsFixture.agent(),
            %Human{human_account_id: paired.human_account_id + 1},
            admin
          ] do
        assert {:error, %Ash.Error.Forbidden{}} = Jobs.cancel_order(order, actor: actor)
      end

      person = %Human{human_account_id: paired.human_account_id}
      assert Jobs.cancel_order!(order, actor: person).state == :cancelled
    end

    test "its agent and the team look now; nobody reads payments directly",
         %{agent: agent, admin: admin} do
      quoted = JobsFixture.quoted(agent, admin, 1_000)

      for actor <- [JobsFixture.agent(), %Human{human_account_id: 1}, nil] do
        assert {:error, %Ash.Error.Forbidden{}} = Jobs.look_now(quoted, actor: actor)
      end

      for actor <- [agent, admin, %System{}] do
        assert {:error, %Ash.Error.Forbidden{}} =
                 quoted
                 |> Ash.Changeset.for_update(:read_payment, %{}, actor: actor)
                 |> Ash.update()
      end
    end

    test "deposits are recorded only by the payment read, and read by the order's readers",
         %{agent: agent, admin: admin} do
      quoted = JobsFixture.quoted(agent, admin, 1_000)
      deposit = deposit_input(quoted)

      for actor <- [agent, admin, nil] do
        assert {:error, %Ash.Error.Forbidden{}} =
                 Deposit
                 |> Ash.Changeset.for_create(:record, deposit, actor: actor)
                 |> Ash.create()
      end

      Deposit |> Ash.Changeset.for_create(:record, deposit, actor: %System{}) |> Ash.create!()

      assert [%Deposit{}] = Jobs.list_deposits!(actor: agent)
      assert [%Deposit{}] = Jobs.list_deposits!(actor: admin)
      assert [] = Jobs.list_deposits!(actor: JobsFixture.agent())
      assert [] = Jobs.list_deposits!(actor: %Human{human_account_id: 1})
    end
  end

  describe "reading payments" do
    setup %{agent: agent, admin: admin} do
      %{quoted: JobsFixture.quoted(agent, admin, 2_500_000)}
    end

    test "a deposit counts once it is deep enough, and then pays the order", %{quoted: quoted} do
      block = @head + 10
      depositor = wallet()

      log =
        JobsFixture.log(
          reference: quoted.payment_reference,
          amount: 2_500_000,
          depositor: depositor,
          block: block
        )

      JobsFixture.node(%{head: block + @confirmations - 2, logs: [log]})
      read!(quoted)
      assert %{state: :quoted, received: received} = reload(quoted)
      assert Decimal.eq?(received, 0)

      JobsFixture.node(%{head: block + @confirmations - 1, logs: [log]})
      read!(quoted)
      order = reload(quoted)
      assert {order.state, is_struct(order.paid_at, DateTime)} == {:paid, true}
      assert Decimal.eq?(order.received, 2_500_000)
      assert order.next_block == block + 1

      assert [deposit] = Jobs.list_deposits!(authorize?: false)
      assert {deposit.order_id, deposit.depositor} == {quoted.id, depositor}
      assert deposit.transaction_hash == log["transactionHash"]
      assert {deposit.log_index, deposit.block_number} == {0, block}
    end

    test "any wallet's deposit with the reference pays, and parts add up", %{quoted: quoted} do
      logs = [
        JobsFixture.log(
          reference: quoted.payment_reference,
          amount: 1_000_000,
          depositor: wallet(),
          block: @head + 1
        ),
        JobsFixture.log(
          reference: quoted.payment_reference,
          amount: 1_000_000,
          depositor: wallet(),
          block: @head + 2
        )
      ]

      # Read up to the second deposit's block exactly; the third comes after.
      JobsFixture.node(%{head: @head + 2 + @confirmations - 1, logs: logs})
      read!(quoted)
      assert %{state: :quoted} = order = reload(quoted)
      assert Decimal.eq?(order.received, 2_000_000)

      third =
        JobsFixture.log(
          reference: quoted.payment_reference,
          amount: 900_000,
          depositor: wallet(),
          block: @head + 3
        )

      JobsFixture.node(%{head: @head + 3 + @confirmations - 1, logs: [third | logs]})
      read!(quoted)

      assert %{state: :paid} = order = reload(quoted)
      assert Decimal.eq?(order.received, 2_900_000)
      assert length(Jobs.list_deposits!(authorize?: false)) == 3
    end

    test "a log read twice is kept once", %{quoted: quoted} do
      log =
        JobsFixture.log(
          reference: quoted.payment_reference,
          amount: 1_000,
          depositor: wallet(),
          block: @head + 1
        )

      JobsFixture.node(%{head: @head + 1 + @confirmations, logs: [log]})
      read!(quoted)

      # Back to the block the quote started at, as a second read of the same
      # blocks would find.
      Repo.query!("UPDATE job_orders SET next_block = $1 WHERE id = $2", [
        @head,
        Ecto.UUID.dump!(quoted.id)
      ])

      read!(quoted)

      assert [_one] = Jobs.list_deposits!(authorize?: false)
    end

    test "a deposit with another tag is not a job payment", %{quoted: quoted} do
      tag = "0x" <> Base.encode16(String.pad_trailing("regent.credits", 32, <<0>>), case: :lower)

      log =
        JobsFixture.log(
          reference: quoted.payment_reference,
          amount: 2_500_000,
          depositor: wallet(),
          block: @head + 1,
          tag: tag
        )

      JobsFixture.node(%{head: @head + 1 + @confirmations, logs: [log]})
      read!(quoted)

      assert %{state: :quoted} = reload(quoted)
      assert [] = Jobs.list_deposits!(authorize?: false)
    end

    test "a quote runs out only once a block made after its expiry is read",
         %{agent: agent, admin: admin} do
      expires_at = DateTime.add(DateTime.utc_now(), -60, :second)
      quoted = JobsFixture.quoted(agent, admin, 2_500_000, expires_at)
      expiry = DateTime.to_unix(expires_at)

      short =
        JobsFixture.log(
          reference: quoted.payment_reference,
          amount: 1_000,
          depositor: wallet(),
          block: @head + 1
        )

      JobsFixture.node(%{
        head: @head + @confirmations + 5,
        logs: [short],
        time: fn _block -> expiry end
      })

      read!(quoted)
      assert %{state: :quoted} = reload(quoted)

      JobsFixture.node(%{
        head: @head + @confirmations + 6,
        logs: [short],
        time: fn _block -> expiry + 1 end
      })

      read!(quoted)
      expired = reload(quoted)
      assert {expired.state, is_struct(expired.expired_at, DateTime)} == {:expired, true}

      # A later deposit is recorded, asked for at once, and changes nothing.
      late =
        JobsFixture.log(
          reference: quoted.payment_reference,
          amount: 2_500_000,
          depositor: wallet(),
          block: @head + 20
        )

      JobsFixture.node(%{head: @head + 20 + @confirmations, logs: [short, late]})

      assert {:ok, _order} = Jobs.look_now(expired, actor: agent)
      assert_enqueued(worker: LookNow, args: %{"primary_key" => %{"id" => quoted.id}})
      assert {:ok, _order} = perform_job(LookNow, %{"primary_key" => %{"id" => quoted.id}})

      assert %{state: :expired} = order = reload(quoted)
      assert Decimal.eq?(order.received, 2_501_000)
    end

    test "a payment read in the same read as the expiry pays", %{agent: agent, admin: admin} do
      quoted =
        JobsFixture.quoted(agent, admin, 1_000, DateTime.add(DateTime.utc_now(), -60, :second))

      log =
        JobsFixture.log(
          reference: quoted.payment_reference,
          amount: 1_000,
          depositor: wallet(),
          block: @head + 1
        )

      JobsFixture.node(%{
        head: @head + 1 + @confirmations,
        logs: [log],
        time: fn _block -> 4_000_000_000 end
      })

      read!(quoted)

      assert %{state: :paid} = reload(quoted)
    end

    @tag :capture_log
    test "a node that cannot be read puts the read off a minute and changes nothing",
         %{quoted: quoted} do
      JobsFixture.node(%{down: true})

      assert {:snooze, 60} =
               perform_job(ReadPayment, %{"primary_key" => %{"id" => quoted.id}})

      assert %{state: :quoted, next_block: @head} = reload(quoted)
    end

    @tag :capture_log
    test "a log that is not a deposit fails the read", %{quoted: quoted} do
      log =
        JobsFixture.log(
          reference: quoted.payment_reference,
          amount: 1_000,
          depositor: wallet(),
          block: @head + 1
        )
        |> Map.put("data", "0x00")

      JobsFixture.node(%{head: @head + 1 + @confirmations, logs: [log]})

      assert_raise Ash.Error.Invalid, ~r/a deposit could not be read/, fn ->
        perform_job(ReadPayment, %{"primary_key" => %{"id" => quoted.id}})
      end

      assert %{state: :quoted, next_block: @head} = reload(quoted)
    end

    test "looking now is for quoted and expired orders", %{agent: agent, admin: admin} do
      assert {:error, %Ash.Error.Invalid{}} =
               Jobs.look_now(JobsFixture.order(agent), actor: agent)

      paid = JobsFixture.quoted(agent, admin, 1_000)

      log =
        JobsFixture.log(
          reference: paid.payment_reference,
          amount: 1_000,
          depositor: wallet(),
          block: @head + 1
        )

      JobsFixture.node(%{head: @head + 1 + @confirmations, logs: [log]})
      read!(paid)

      assert {:error, %Ash.Error.Invalid{}} = Jobs.look_now(reload(paid), actor: agent)
    end
  end

  test "the minute-by-minute read is off unless the build turns it on" do
    refute Code.ensure_loaded?(Techtree.Jobs.Order.Schedulers.ReadPayment)
  end

  describe "paying" do
    test "a quoted order's calls; any other order has none", %{agent: agent, admin: admin} do
      quoted = JobsFixture.quoted(agent, admin, 1_000)

      assert {:ok, [%{step: "approve", chain_id: 8453}, %{step: "deposit", chain_id: 8453}]} =
               Payment.calls(quoted)

      assert {:error, :not_quoted} = Payment.calls(JobsFixture.order(agent))
    end

    test "whether staking is paused is read at the newest block" do
      JobsFixture.node(%{head: @head, paused: false})
      assert {:ok, false} = Techtree.Jobs.Staking.paused()

      JobsFixture.node(%{head: @head, paused: true})
      assert {:ok, true} = Techtree.Jobs.Staking.paused()
    end
  end

  defp read!(order) do
    assert {:ok, _order} = perform_job(ReadPayment, %{"primary_key" => %{"id" => order.id}})
  end

  defp reload(order),
    do: Ash.load!(Ash.reload!(order, authorize?: false), :received, authorize?: false)

  defp wallet, do: "0x" <> Base.encode16(:crypto.strong_rand_bytes(20), case: :lower)

  defp deposit_input(order) do
    %{
      order_id: order.id,
      transaction_hash: "0x" <> Base.encode16(:crypto.strong_rand_bytes(32), case: :lower),
      log_index: 0,
      depositor: wallet(),
      amount: 1_000,
      block_number: @head + 1
    }
  end
end
