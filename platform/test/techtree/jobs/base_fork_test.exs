defmodule Techtree.Jobs.BaseForkTest do
  # Job payments end to end on a local fork of Base (`Techtree.BaseFork`): the
  # calls `Techtree.Jobs.Payment` builds are sent to the real USDC and REGENT
  # revenue staking contracts on the fork, and the payment read finds them.
  # - the agent's own wallet pays, and the order is paid;
  # - another wallet (the founder paying by hand) pays, and the order is paid;
  # - too little leaves the order quoted, with the deposit recorded;
  # - a deposit with another tag is not a job payment.
  #
  # Needs anvil and Base's public node: `mix test --only base_fork`.
  use Techtree.DataCase, async: false
  use Oban.Testing, repo: Techtree.Repo

  alias RegentChain.Call
  alias Techtree.{BaseFork, Jobs, JobsFixture}
  alias Techtree.Jobs.Order.Workers.ReadPayment
  alias Techtree.Jobs.{Payment, Staking}

  @moduletag :base_fork
  @moduletag timeout: 180_000

  @quote 2_500_000

  setup_all do
    %{fork: BaseFork.start!()}
  end

  setup do
    admin_id = "did:privy:jobs-fork-admin-" <> Ecto.UUID.generate()
    JobsFixture.put_admins([admin_id])
    agent = JobsFixture.agent()
    admin = %RegentAgents.Person{privy_user_id: admin_id, role: :admin}

    %{agent: agent, quoted: JobsFixture.quoted(agent, admin, @quote)}
  end

  test "staking takes deposits on the fork" do
    assert {:ok, false} = Staking.paused()
  end

  test "the agent's own wallet pays, and the order is paid", %{fork: fork, agent: agent} = c do
    {:ok, calls} = Payment.calls(c.quoted)
    BaseFork.fund(fork, agent.wallet_address, @quote)
    [_approve, deposit] = BaseFork.send!(fork, agent.wallet_address, calls)

    order = settle(fork, c.quoted)

    assert {order.state, Decimal.eq?(order.received, @quote)} == {:paid, true}

    assert [%{depositor: depositor, transaction_hash: ^deposit}] =
             Jobs.list_deposits!(authorize?: false)

    assert depositor == agent.wallet_address
  end

  test "another wallet pays with the order's reference, and the order is paid",
       %{fork: fork} = c do
    founder = wallet()
    {:ok, calls} = Payment.calls(c.quoted)
    BaseFork.fund(fork, founder, @quote)
    BaseFork.send!(fork, founder, calls)

    order = settle(fork, c.quoted)

    assert order.state == :paid
    assert [%{depositor: ^founder}] = Jobs.list_deposits!(authorize?: false)
  end

  test "too little leaves the order quoted, with the deposit recorded", %{fork: fork} = c do
    payer = wallet()
    {:ok, calls} = Payment.calls(%{c.quoted | quote_amount: @quote - 1})
    BaseFork.fund(fork, payer, @quote)
    BaseFork.send!(fork, payer, calls)

    order = settle(fork, c.quoted)

    assert {order.state, Decimal.eq?(order.received, @quote - 1)} == {:quoted, true}
  end

  test "a deposit with another tag is not a job payment", %{fork: fork} = c do
    payer = wallet()
    {:ok, [approve, _deposit]} = Payment.calls(c.quoted)

    credits =
      "0x" <> Base.encode16(String.pad_trailing("regent.credits", 32, <<0>>), case: :lower)

    deposit =
      RegentChain.Review.step(
        "deposit",
        Payment.config()[:staking],
        Call.encode("depositUSDC(uint256,bytes32,bytes32)", [
          @quote,
          credits,
          c.quoted.payment_reference
        ])
      )

    BaseFork.fund(fork, payer, @quote)
    BaseFork.send!(fork, payer, [approve, deposit])

    order = settle(fork, c.quoted)

    assert {order.state, Decimal.eq?(order.received, 0)} == {:quoted, true}
    assert [] = Jobs.list_deposits!(authorize?: false)
  end

  # Buries the deposits deep enough to count, then runs the payment read.
  defp settle(fork, quoted) do
    BaseFork.mine(fork, Payment.config()[:confirmations])
    assert {:ok, _order} = perform_job(ReadPayment, %{"primary_key" => %{"id" => quoted.id}})
    quoted |> Ash.reload!(authorize?: false) |> Ash.load!(:received, authorize?: false)
  end

  defp wallet, do: "0x" <> Base.encode16(:crypto.strong_rand_bytes(20), case: :lower)
end
