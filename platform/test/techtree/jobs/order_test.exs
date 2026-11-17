defmodule Techtree.Jobs.OrderTest do
  # Job orders through the domain's actions:
  # - an agent asks, the team checks and quotes, and the quote gives the order
  #   its payment reference;
  # - each move is allowed only from the states it starts from;
  # - who may ask, read, quote, refuse, cancel, look now, and settle;
  # - looking now asks the one reading job to run soon, and only once the
  #   reader is on;
  # - the calls that pay, and whether staking takes deposits.
  use Techtree.DataCase, async: false
  use Oban.Testing, repo: Techtree.Repo

  alias Techtree.Jobs
  alias Techtree.Jobs.{Deposit, Order, Payment, ReadPayments}
  alias Techtree.Actors.{Human, System}
  alias Techtree.{JobsFixture, NetworkFixture}

  setup do
    admin_id = "did:privy:jobs-admin-" <> Ecto.UUID.generate()
    JobsFixture.put_admins([admin_id])

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

    test "an order cancelled since the reader found it is not settled",
         %{agent: agent, admin: admin} do
      quoted = JobsFixture.quoted(agent, admin, 1_000)
      Jobs.record_deposit!(deposit_input(quoted.payment_reference), actor: %System{})
      Jobs.cancel_order!(quoted, actor: agent)

      assert {:error, error} = Jobs.settle_order(quoted, nil, actor: %System{})
      assert [%Ash.Error.Changes.StaleRecord{}] = Ash.Error.to_error_class(error).errors
      assert Ash.reload!(quoted, authorize?: false).state == :cancelled
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

    test "its agent and the team look now; only the payment reader finds and settles orders",
         %{agent: agent, admin: admin} do
      quoted = JobsFixture.quoted(agent, admin, 1_000)

      for actor <- [JobsFixture.agent(), %Human{human_account_id: 1}, nil] do
        assert {:error, %Ash.Error.Forbidden{}} = Jobs.look_now(quoted, actor: actor)
      end

      for actor <- [agent, admin, nil] do
        assert {:ok, []} = Jobs.due_orders([quoted.payment_reference], nil, actor: actor)
        assert {:error, %Ash.Error.Forbidden{}} = Jobs.settle_order(quoted, nil, actor: actor)
      end

      assert {:ok, [%Order{id: id}]} =
               Jobs.due_orders([quoted.payment_reference], nil, actor: %System{})

      assert id == quoted.id
    end

    test "deposits are saved only by the payment reader, and read by the order's readers",
         %{agent: agent, admin: admin} do
      quoted = JobsFixture.quoted(agent, admin, 1_000)
      deposit = deposit_input(quoted.payment_reference)
      unmatched = deposit_input(JobsFixture.word())

      for actor <- [agent, admin, nil] do
        assert {:error, %Ash.Error.Forbidden{}} = Jobs.record_deposit(deposit, actor: actor)
      end

      Jobs.record_deposit!(deposit, actor: %System{})
      Jobs.record_deposit!(unmatched, actor: %System{})

      for actor <- [agent, admin, nil] do
        assert {:ok, []} = Jobs.seen_deposits(8453, deposit.contract, 0, 2_000, [], actor: actor)
      end

      assert {:ok, [_, _]} =
               Jobs.seen_deposits(8453, deposit.contract, 0, 2_000, [], actor: %System{})

      assert [%Deposit{reference: reference}] = Jobs.list_deposits!(actor: agent)
      assert reference == quoted.payment_reference
      assert [_, _] = Jobs.list_deposits!(actor: admin)
      assert [] = Jobs.list_deposits!(actor: JobsFixture.agent())
      assert [] = Jobs.list_deposits!(actor: %Human{human_account_id: 1})
    end

    test "a saved deposit is kept as first saved, and nothing changes or removes it",
         %{agent: agent, admin: admin} do
      quoted = JobsFixture.quoted(agent, admin, 1_000)
      deposit = deposit_input(quoted.payment_reference)
      first = Jobs.record_deposit!(deposit, actor: %System{})

      again =
        Jobs.record_deposit!(%{deposit | amount: 5_000, depositor: JobsFixture.wallet()},
          actor: %System{}
        )

      assert again.id == first.id
      assert [%{amount: amount, depositor: depositor}] = Jobs.list_deposits!(actor: admin)
      assert {Decimal.to_integer(amount), depositor} == {1_000, deposit.depositor}

      refute Enum.any?(Ash.Resource.Info.actions(Deposit), &(&1.type in [:update, :destroy]))
    end
  end

  describe "looking now" do
    test "is for quoted and expired orders", %{agent: agent, admin: admin} do
      assert {:error, %Ash.Error.Invalid{}} =
               Jobs.look_now(JobsFixture.order(agent), actor: agent)

      cancelled = agent |> JobsFixture.quoted(admin, 1_000) |> Jobs.cancel_order!(actor: agent)
      assert {:error, %Ash.Error.Invalid{}} = Jobs.look_now(cancelled, actor: agent)
    end

    test "asks for nothing while the reader is off", %{agent: agent, admin: admin} do
      quoted = JobsFixture.quoted(agent, admin, 1_000)

      assert {:ok, _order} = Jobs.look_now(quoted, actor: agent)
      refute_enqueued(worker: ReadPayments)
    end

    test "starts the one reading job, or brings it to ten seconds away and never later",
         %{agent: agent, admin: admin} do
      JobsFixture.read_payments()
      quoted = JobsFixture.quoted(agent, admin, 1_000)

      assert {:ok, _order} = Jobs.look_now(quoted, actor: agent)
      assert [%{state: "available"} = job] = all_enqueued(worker: ReadPayments)
      assert job.args == JobsFixture.reader()

      # Waiting out its five minutes, the job is brought forward to ten
      # seconds away.
      later = DateTime.add(DateTime.utc_now(), 300)
      park(job, later)
      assert {:ok, _order} = Jobs.look_now(quoted, actor: admin)
      assert [%{id: id, scheduled_at: soon}] = all_enqueued(worker: ReadPayments)
      assert id == job.id
      assert DateTime.diff(soon, DateTime.utc_now()) in 8..10

      # Due sooner than that, it keeps its time.
      sooner = DateTime.add(DateTime.utc_now(), 3)
      park(job, sooner)
      assert {:ok, _order} = Jobs.look_now(quoted, actor: agent)
      assert [%{scheduled_at: ^sooner}] = all_enqueued(worker: ReadPayments)
    end
  end

  describe "paying" do
    test "a quoted order's calls; any other order has none", %{agent: agent, admin: admin} do
      quoted = JobsFixture.quoted(agent, admin, 1_000)

      assert {:ok, [%{step: "approve", chain_id: 8453}, %{step: "deposit", chain_id: 8453}]} =
               Payment.calls(quoted)

      assert {:error, :not_quoted} = Payment.calls(JobsFixture.order(agent))
    end

    test "whether staking is paused is read at the newest block" do
      JobsFixture.node(%{head: 1, paused: false})
      assert {:ok, false} = Techtree.Jobs.Staking.paused()

      JobsFixture.node(%{head: 1, paused: true})
      assert {:ok, true} = Techtree.Jobs.Staking.paused()
    end
  end

  # The reading job as a pass leaves it: waiting until `at`. Oban's job table
  # has no Ash resource.
  defp park(job, at) do
    Oban.Job
    |> where(id: ^job.id)
    |> Repo.update_all([set: [state: "scheduled", scheduled_at: at]],
      prefix: Oban.config().prefix
    )
  end

  defp deposit_input(reference) do
    %{
      chain_id: 8453,
      contract: Payment.config()[:staking],
      transaction_hash: JobsFixture.word(),
      log_index: 0,
      block_number: 1_000,
      block_hash: JobsFixture.block_hash(1_000),
      depositor: JobsFixture.wallet(),
      reference: reference,
      amount: 1_000
    }
  end
end
