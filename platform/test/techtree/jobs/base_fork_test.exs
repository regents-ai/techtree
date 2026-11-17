defmodule Techtree.Jobs.BaseForkTest do
  # Job payments end to end on a local fork of Base (`Techtree.BaseFork`): the
  # calls `Techtree.Jobs.Payment` builds are sent to the real USDC and REGENT
  # revenue staking contracts on the fork, and the payment reader's job finds
  # them at the latest block.
  # - the agent's own wallet pays, and the order is paid;
  # - another wallet (the founder paying by hand) pays, and the order is paid;
  # - too little leaves the order quoted, with the deposit saved;
  # - a deposit with another tag is not a job payment;
  # - two passes over the same blocks count the deposit once;
  # - a deposit whose reference matches no order is saved with none.
  #
  # Needs anvil and Base's public node: `mix test --only base_fork`.
  use Techtree.DataCase, async: false
  use Oban.Testing, repo: Techtree.Repo

  alias RegentChain.Call
  alias Techtree.{BaseFork, Jobs, JobsFixture}
  alias Techtree.Jobs.{Payment, ReadPayments, Staking}

  @moduletag :base_fork
  @moduletag timeout: 180_000

  @quote 2_500_000

  setup_all do
    %{fork: BaseFork.start!()}
  end

  setup %{fork: fork} do
    admin_id = "did:privy:jobs-fork-admin-" <> Ecto.UUID.generate()
    JobsFixture.put_admins([admin_id])
    agent = JobsFixture.agent()
    admin = %RegentAgents.Person{privy_user_id: admin_id, role: :admin}
    quoted = JobsFixture.quoted(agent, admin, @quote)
    # The reader's first run opens its cursor at the fork's head and reads back
    # 300 blocks: past them, it finds no earlier test's payments on the fork
    # and never reads blocks from Base's own node.
    BaseFork.mine(fork, 301)
    read!()

    %{agent: agent, quoted: quoted}
  end

  test "staking takes deposits on the fork" do
    assert {:ok, false} = Staking.paused()
  end

  test "the agent's own wallet pays, and the order is paid", %{fork: fork, agent: agent} = c do
    {:ok, calls} = Payment.calls(c.quoted)
    BaseFork.fund(fork, agent.wallet_address, @quote)
    [_approve, deposit] = BaseFork.send!(fork, agent.wallet_address, calls)

    read!()
    order = reload(c.quoted)

    assert {order.state, Decimal.eq?(order.received, @quote)} == {:paid, true}
    assert [%{depositor: depositor, transaction_hash: ^deposit}] = deposits()
    assert depositor == agent.wallet_address
  end

  test "another wallet pays with the order's reference, and the order is paid",
       %{fork: fork} = c do
    founder = JobsFixture.wallet()
    {:ok, calls} = Payment.calls(c.quoted)
    BaseFork.fund(fork, founder, @quote)
    BaseFork.send!(fork, founder, calls)

    read!()

    assert %{state: :paid} = reload(c.quoted)
    assert [%{depositor: ^founder}] = deposits()
  end

  test "too little leaves the order quoted, with the deposit saved", %{fork: fork} = c do
    payer = JobsFixture.wallet()
    {:ok, calls} = Payment.calls(%{c.quoted | quote_amount: @quote - 1})
    BaseFork.fund(fork, payer, @quote)
    BaseFork.send!(fork, payer, calls)

    read!()
    order = reload(c.quoted)

    assert {order.state, Decimal.eq?(order.received, @quote - 1)} == {:quoted, true}
    assert [_deposit] = deposits()
  end

  test "a deposit with another tag is not a job payment", %{fork: fork} = c do
    payer = JobsFixture.wallet()
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

    read!()
    order = reload(c.quoted)

    assert {order.state, Decimal.eq?(order.received, 0)} == {:quoted, true}
    assert [] = deposits()
  end

  test "two passes over the same blocks count the deposit once", %{fork: fork} = c do
    payer = JobsFixture.wallet()
    {:ok, calls} = Payment.calls(c.quoted)
    BaseFork.fund(fork, payer, @quote)
    [_approve, deposit] = BaseFork.send!(fork, payer, calls)

    read!()
    BaseFork.mine(fork, 5)
    read!()
    order = reload(c.quoted)

    assert {order.state, Decimal.eq?(order.received, @quote)} == {:paid, true}
    assert [%{transaction_hash: ^deposit}] = deposits()
  end

  test "a deposit whose reference matches no order is saved with none", %{fork: fork} = c do
    payer = JobsFixture.wallet()
    unknown = JobsFixture.word()
    {:ok, calls} = Payment.calls(%{c.quoted | payment_reference: unknown})
    BaseFork.fund(fork, payer, @quote)
    BaseFork.send!(fork, payer, calls)

    read!()

    assert [%{reference: ^unknown, order: nil, depositor: ^payer}] = deposits()
    assert %{state: :quoted} = reload(c.quoted)
  end

  defp read!, do: assert({:snooze, 300} = perform_job(ReadPayments, JobsFixture.reader()))

  defp deposits, do: Jobs.list_deposits!(authorize?: false, load: [:order])

  defp reload(order),
    do: order |> Ash.reload!(authorize?: false) |> Ash.load!(:received, authorize?: false)
end
