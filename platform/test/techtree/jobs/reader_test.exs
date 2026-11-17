defmodule Techtree.Jobs.ReaderTest do
  # The job payments reader against a stand-in Base node, run as its one
  # reading job (`Techtree.Jobs.ReadPayments`):
  # - the cursor opens at the head on the first run, reading back the last 300
  #   blocks only;
  # - every job payment is saved once, whoever sent it and whatever reference it
  #   carries, and moves the order it pays; passes over the same blocks save
  #   nothing twice;
  # - a day behind is read in stretches of at most 10,000 blocks, each reading
  #   the last 300 again; a refused range is asked for in halves;
  # - a saved transaction that no longer matches is kept as first saved and
  #   named once, by the pass that reads its block for the last time;
  # - nothing is passed over: a log that does not read, or a block the node
  #   keeps refusing, ends the pass with nothing of its stretch saved;
  # - a quote runs out only once a block made after its expiry is read;
  # - a node that does not answer, one on another chain, and a cursor another
  #   pass moved first;
  # - what each pass reports, and the watch that keeps the job.
  use Techtree.DataCase, async: false
  use Oban.Testing, repo: Techtree.Repo
  use ExUnitProperties

  import ExUnit.CaptureLog

  alias Techtree.Jobs
  alias Techtree.Jobs.{Payment, ReadPayments, Reader, Watch}
  alias Techtree.Actors.System
  alias Techtree.JobsFixture

  @head 40_000_000

  setup do
    admin_id = "did:privy:jobs-reader-admin-" <> Ecto.UUID.generate()
    JobsFixture.put_admins([admin_id])
    admin = %RegentAgents.Person{privy_user_id: admin_id, role: :admin}

    %{admin: admin, agent: JobsFixture.agent(), staking: Payment.config()[:staking]}
  end

  describe "the first run" do
    test "opens the cursor at the head, reading back only the last 300 blocks",
         %{agent: agent, admin: admin, staking: staking} do
      quoted = JobsFixture.quoted(agent, admin, 1_000)
      before = log(quoted, 400, @head - 301)
      within = log(quoted, 500, @head - 300)

      read!(%{head: @head, logs: [before, within]})

      assert_received {:logs_asked, from, @head}
      assert from == @head - 300

      cursor = cursor()
      assert {cursor.next_block, cursor.head_block} == {@head + 1, @head}
      assert cursor.head_block_hash == JobsFixture.block_hash(@head)
      assert DateTime.diff(DateTime.utc_now(), cursor.observed_at) in 0..5
      assert [%{transaction_hash: hash}] = deposits()
      assert hash == within["transactionHash"]
      assert cursor.contract == staking
    end
  end

  describe "saving payments" do
    setup %{agent: agent, admin: admin} do
      read!(%{head: @head})
      %{quoted: JobsFixture.quoted(agent, admin, 2_500_000)}
    end

    test "any wallet's deposits with the reference add up and pay the order, kept as the chain said",
         %{quoted: quoted, staking: staking} do
      first = log(quoted, 1_000_000, @head + 1)
      second = log(quoted, 1_000_000, @head + 2, log_index: 3)
      read!(%{head: @head + 2, logs: [first, second]})

      assert %{state: :quoted} = order = reload(quoted)
      assert Decimal.eq?(order.received, 2_000_000)

      third = log(quoted, 900_000, @head + 3)
      read!(%{head: @head + 3, logs: [first, second, third]})

      order = reload(quoted)
      assert {order.state, is_struct(order.paid_at, DateTime)} == {:paid, true}
      assert Decimal.eq?(order.received, 2_900_000)

      assert [one, two, three] = deposits()
      assert one.transaction_hash == first["transactionHash"]
      assert one.depositor == "0x" <> String.slice(Enum.at(first["topics"], 2), -40, 40)

      assert {one.chain_id, one.contract, one.reference} ==
               {8453, staking, quoted.payment_reference}

      assert {two.block_number, two.block_hash, two.log_index} ==
               {@head + 2, JobsFixture.block_hash(@head + 2), 3}

      assert Decimal.eq?(three.amount, 900_000)
      assert length(Enum.uniq([one.depositor, two.depositor, three.depositor])) == 3
    end

    test "passes over the same blocks save nothing twice", %{quoted: quoted} do
      chain = %{head: @head + 10, logs: [log(quoted, 2_500_000, @head + 1)]}

      read!(chain)
      read!(chain)
      read!(%{chain | head: @head + 20})

      assert %{state: :paid} = order = reload(quoted)
      assert Decimal.eq?(order.received, 2_500_000)
      assert [_one] = deposits()
    end

    test "a deposit whose reference matches no order is saved with none", %{quoted: quoted} do
      unknown = JobsFixture.word()

      read!(%{
        head: @head + 5,
        logs: [JobsFixture.log(reference: unknown, amount: 2_500_000, block: @head + 1)]
      })

      assert [deposit] = deposits()
      assert {deposit.reference, deposit.order} == {unknown, nil}
      assert %{state: :quoted} = reload(quoted)
    end

    test "a deposit with another tag is not a job payment", %{quoted: quoted} do
      credits =
        "0x" <> Base.encode16(String.pad_trailing("regent.credits", 32, <<0>>), case: :lower)

      read!(%{head: @head + 5, logs: [log(quoted, 2_500_000, @head + 1, tag: credits)]})

      assert [] = deposits()
      assert %{state: :quoted} = reload(quoted)
    end
  end

  describe "stretches" do
    setup do
      read!(%{head: @head})
      # Only the searches the test's own pass asks for.
      asked()
      :ok
    end

    test "a day behind is read in stretches of at most 10,000 blocks, each reading the last 300 again",
         %{agent: agent, admin: admin} do
      quoted = JobsFixture.quoted(agent, admin, 3_000)
      day = 432_000
      blocks = [@head + 5, @head + 200_000, @head + day]
      read!(%{head: @head + day, logs: Enum.map(blocks, &log(quoted, 1_000, &1))})

      asked = asked()
      assert hd(asked) == {@head + 1 - 300, @head + 1 - 300 + 9_999}
      assert Enum.all?(asked, fn {from, to} -> to - from + 1 <= 10_000 end)
      assert elem(List.last(asked), 1) == @head + day

      for [{_from, to}, {next_from, _to}] <- Enum.chunk_every(asked, 2, 1, :discard) do
        assert next_from == to + 1 - 300
      end

      assert %{state: :paid} = reload(quoted)
      assert length(deposits()) == 3
      assert cursor().next_block == @head + day + 1
    end

    test "a range the node refuses is asked for in halves", %{agent: agent, admin: admin} do
      quoted = JobsFixture.quoted(agent, admin, 2_000)

      read!(%{
        head: @head + 5_000,
        logs: [log(quoted, 1_000, @head + 100), log(quoted, 1_000, @head + 4_900)],
        refuse_over: 2_000
      })

      asked = asked()
      assert hd(asked) == {@head - 299, @head + 5_000}
      assert Enum.any?(asked, fn {from, to} -> to - from + 1 <= 2_000 end)
      assert %{state: :paid} = reload(quoted)
      assert cursor().next_block == @head + 5_001
    end
  end

  describe "a saved transaction that no longer matches" do
    setup %{agent: agent, admin: admin} do
      read!(%{head: @head})
      quoted = JobsFixture.quoted(agent, admin, 1_000)
      saved = log(quoted, 1_000, @head + 1)
      read!(%{head: @head + 10, logs: [saved]})

      %{quoted: quoted, saved: saved}
    end

    test "with other values is kept and named once", %{saved: saved} = context do
      changed = %{saved | "data" => JobsFixture.log(reference: "0x", amount: 7, block: 1)["data"]}
      named_once(context, [changed])
    end

    test "moved to another block is kept, named once and never saved again",
         %{saved: saved} = context do
      moved =
        JobsFixture.log(
          reference: Enum.at(saved["topics"], 3),
          amount: 1_000,
          block: @head + 350,
          transaction_hash: saved["transactionHash"]
        )

      named_once(context, [moved])
    end

    test "in its block, whose hash changed, is kept and named once", %{saved: saved} = context do
      named_once(context, [%{saved | "blockHash" => JobsFixture.word()}])
    end

    test "gone is kept and named once", context do
      named_once(context, [])
    end

    # Three passes on the changed chain: the first still reads the block again
    # later and names nothing; the second reads it for the last time and names
    # the transaction once; the third no longer reads it.
    defp named_once(%{quoted: quoted, saved: saved, staking: staking}, logs) do
      warnings =
        capture_log(fn ->
          for head <- [@head + 100, @head + 400, @head + 800],
              do: read!(%{head: head, logs: logs})
        end)

      named = Regex.scan(~r/#{saved["transactionHash"]}/, warnings)
      assert length(named) == 1
      assert warnings =~ staking

      assert [deposit] = deposits()

      assert {deposit.transaction_hash, deposit.block_number} ==
               {saved["transactionHash"], @head + 1}

      assert deposit.block_hash == JobsFixture.block_hash(@head + 1)
      assert Decimal.eq?(deposit.amount, 1_000)
      assert %{state: :paid} = reload(quoted)
      assert cursor().next_block == @head + 801
    end
  end

  describe "nothing is passed over" do
    setup %{agent: agent, admin: admin} do
      read!(%{head: @head})
      %{quoted: JobsFixture.quoted(agent, admin, 1_000)}
    end

    test "a log that does not read as a deposit ends the pass", %{quoted: quoted} do
      unreadable = %{log(quoted, 1_000, @head + 2) | "data" => "0x00"}
      JobsFixture.node(%{head: @head + 10, logs: [log(quoted, 1_000, @head + 1), unreadable]})

      assert {:error, {:unreadable_log, hash}} = perform_job(ReadPayments, JobsFixture.reader())
      assert hash == unreadable["transactionHash"]
      assert [] = deposits()
      assert cursor().next_block == @head + 1
    end

    test "one block the node keeps refusing ends the pass", %{quoted: quoted} do
      JobsFixture.node(%{
        head: @head + 100,
        logs: [log(quoted, 1_000, @head + 10)],
        refuse: [@head + 50]
      })

      asked()
      assert {:error, {:refused, _error}} = perform_job(ReadPayments, JobsFixture.reader())
      assert List.last(asked()) == {@head + 50, @head + 50}
      assert [] = deposits()
      assert cursor().next_block == @head + 1
    end
  end

  describe "a quote's expiry" do
    test "is reached only once a block made after it is read; later deposits change nothing",
         %{agent: agent, admin: admin} do
      expires_at = DateTime.add(DateTime.utc_now(), -60, :second)
      quoted = JobsFixture.quoted(agent, admin, 2_500_000, expires_at)
      expiry = DateTime.to_unix(expires_at)

      read!(%{head: @head, time: expiry})
      assert %{state: :quoted} = reload(quoted)

      short = log(quoted, 1_000, @head + 1)
      read!(%{head: @head + 1, time: expiry + 1, logs: [short]})
      expired = reload(quoted)
      assert {expired.state, is_struct(expired.expired_at, DateTime)} == {:expired, true}

      late = log(quoted, 2_500_000, @head + 20)
      read!(%{head: @head + 20, logs: [short, late]})

      assert %{state: :expired} = order = reload(quoted)
      assert Decimal.eq?(order.received, 2_501_000)
    end

    test "a payment saved as it is reached pays", %{agent: agent, admin: admin} do
      expires_at = DateTime.add(DateTime.utc_now(), -60, :second)
      quoted = JobsFixture.quoted(agent, admin, 1_000, expires_at)
      read!(%{head: @head, time: DateTime.to_unix(expires_at) - 10})

      read!(%{head: @head + 1, logs: [log(quoted, 1_000, @head + 1)]})

      assert %{state: :paid} = reload(quoted)
    end
  end

  describe "the reading job" do
    @tag :capture_log
    test "waits a minute when the node does not answer, with one warning" do
      for chain <- [%{down: true}, %{status: 503}, %{status: 429}] do
        JobsFixture.node(chain)

        warnings =
          capture_log(fn ->
            assert {:snooze, 60} = perform_job(ReadPayments, JobsFixture.reader())
          end)

        assert [_one] = Regex.scan(~r/did not answer/, warnings)
      end

      assert {:ok, nil} = Jobs.get_cursor(8453, Payment.config()[:staking], actor: %System{})
    end

    @tag :capture_log
    test "never reads a node that serves another chain" do
      JobsFixture.node(%{head: @head, chain_id: 1})

      assert {:cancel, {:wrong_chain, 1}} = perform_job(ReadPayments, JobsFixture.reader())
      assert {:ok, nil} = Jobs.get_cursor(8453, Payment.config()[:staking], actor: %System{})
    end

    test "saves nothing when another pass moved the cursor first", %{agent: agent, admin: admin} do
      read!(%{head: @head})
      quoted = JobsFixture.quoted(agent, admin, 1_000)
      other_pass = @head + 5

      read!(%{
        head: @head + 10,
        logs: [log(quoted, 1_000, @head + 1)],
        on_logs: fn -> move_cursor(@head + 1, other_pass) end
      })

      assert [] = deposits()
      assert %{state: :quoted} = reload(quoted)
      assert cursor().next_block == other_pass
    end

    test "reports how far the record trails the head after each pass" do
      ref = :telemetry_test.attach_event_handlers(self(), [[:techtree, :indexer, :lag]])
      on_exit(fn -> :telemetry.detach(ref) end)

      read!(%{head: @head})

      assert_received {[:techtree, :indexer, :lag], ^ref, %{blocks: 0},
                       %{indexer: "job_payments", chain_id: 8453}}
    end

    test "is kept by the watch, one job for the contract" do
      assert :ok = perform_job(Watch, %{})
      assert :ok = perform_job(Watch, %{})

      assert [%{args: args, queue: "jobs_chain"}] = all_enqueued(worker: ReadPayments)
      assert args == JobsFixture.reader()
    end

    test "is not scheduled while the reader is off" do
      crontab = Application.fetch_env!(:techtree, Oban)[:cron][:crontab]
      refute Enum.any?(crontab, &match?({_schedule, Watch}, &1))
    end
  end

  property "every job payment is saved once, and an order is paid exactly when they reach its quote",
           %{agent: agent, admin: admin} do
    check all(
            quote <- integer(1..5_000),
            payments <- list_of({integer(1..2_000), integer(1..2_000)}, max_length: 6),
            steps <- list_of(integer(0..900), min_length: 1, max_length: 5),
            max_runs: 15
          ) do
      contract = JobsFixture.wallet()
      reader = %{chain_id: 8453, contract: contract}
      quoted = JobsFixture.quoted(agent, admin, quote)

      logs =
        for {offset, amount} <- payments do
          log(quoted, amount, @head + offset, contract: contract)
        end

      JobsFixture.node(%{head: @head, logs: logs})
      assert :ok = Reader.pass(reader)

      Enum.reduce(steps ++ [2_000], @head, fn step, head ->
        head = head + step
        JobsFixture.node(%{head: head, logs: logs})
        assert :ok = Reader.pass(reader)

        made = for {offset, amount} <- payments, @head + offset <= head, do: amount
        saved = Jobs.list_deposits!(authorize?: false, query: [filter: [contract: contract]])

        assert Enum.sort(Enum.map(saved, &Decimal.to_integer(&1.amount))) == Enum.sort(made)
        assert reload(quoted).state == if(Enum.sum(made) >= quote, do: :paid, else: :quoted)
        head
      end)
    end
  end

  defp read!(chain) do
    JobsFixture.node(chain)
    assert {:snooze, 300} = perform_job(ReadPayments, JobsFixture.reader())
  end

  defp log(order, amount, block, fields \\ []) do
    JobsFixture.log([reference: order.payment_reference, amount: amount, block: block] ++ fields)
  end

  defp asked(found \\ []) do
    receive do
      {:logs_asked, from, to} -> asked([{from, to} | found])
    after
      0 -> Enum.reverse(found)
    end
  end

  defp cursor, do: Jobs.get_cursor!(8453, Payment.config()[:staking], actor: %System{})

  # Another machine's pass, moving the cursor on from `from`.
  defp move_cursor(from, to) do
    case cursor() do
      %{next_block: ^from} = cursor ->
        Jobs.advance_cursor!(
          cursor,
          %{
            from: from,
            next_block: to,
            head_block: to,
            head_block_hash: JobsFixture.block_hash(to),
            observed_at: DateTime.utc_now()
          },
          actor: %System{}
        )

      _moved ->
        :ok
    end
  end

  defp deposits do
    [authorize?: false, load: [:order]]
    |> Jobs.list_deposits!()
    |> Enum.sort_by(&{&1.block_number, &1.log_index})
  end

  defp reload(order),
    do: Ash.load!(Ash.reload!(order, authorize?: false), :received, authorize?: false)
end
