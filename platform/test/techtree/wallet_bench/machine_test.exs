defmodule Techtree.WalletBench.MachineTest do
  # The readiness rules of plan D18: a machine is ready only after its baseline
  # is built and has settled a minute after its checkpoint, its boot id has held for 30 seconds, a file reads back exactly and
  # the tested account cannot reach the bench; a machine that restarted in
  # between is failed at once, never retried. Every step leaves its event.
  use Techtree.DataCase, async: false
  use Oban.Testing, repo: Techtree.Repo

  alias Techtree.WalletBench
  alias Techtree.WalletBench.Machine

  @name "wb-test-h05"

  setup do
    previous = Application.get_env(:regent_sprites, :req_options)
    Application.put_env(:regent_sprites, :token, "test-sprites-token")
    Application.put_env(:regent_sprites, :req_options, plug: {Req.Test, __MODULE__})
    Req.Test.stub(__MODULE__, &sprites/1)
    Process.put(:boot_ids, ["boot-1"])
    Process.put(:baseline, "missing")

    on_exit(fn ->
      Application.delete_env(:regent_sprites, :token)

      if previous,
        do: Application.put_env(:regent_sprites, :req_options, previous),
        else: Application.delete_env(:regent_sprites, :req_options)
    end)
  end

  test "a requested machine is created, built, checkpointed, restored and ready, one event per step" do
    machine = WalletBench.request_machine!(@name, "H05", authorize?: false)
    assert_enqueued(worker: Machine.Workers.CreateSprite)

    # The chain runs up to readiness, which waits for the boot id to settle.
    build(machine)
    settling = WalletBench.get_machine!(machine.id, authorize?: false)
    assert settling.state == :settling
    assert settling.baseline_checkpoint_id == "v2"
    assert settling.boot_id == "boot-1"

    settle(machine)
    drain(with_scheduled: true)

    ready = WalletBench.get_machine!(machine.id, authorize?: false)
    assert ready.state == :ready
    assert ready.sprite_version == "0.0.1-rc48"
    assert ready.manifest["harness_version"] == "2.1.286 (Claude Code)"
    assert ready.recipe_digest == "digest-1"

    events = WalletBench.list_machine_events!(machine.id, authorize?: false)

    assert Enum.map(events, & &1.step) ==
             [:requested, :created, :built, :checkpointed, :restored, :settling, :ready]

    assert List.last(events).detail["upload_round_trip"] == true
  end

  test "a machine that restarted after its restore is failed at once, with the reason" do
    machine = WalletBench.request_machine!(@name, "H05", authorize?: false)
    build(machine)

    Process.put(:boot_ids, ["boot-2"])
    settle(machine)
    drain(with_scheduled: true)

    failed = WalletBench.get_machine!(machine.id, authorize?: false)
    assert failed.state == :failed
    assert failed.failure == "The machine restarted after its restore."
    refute_enqueued(worker: Machine.Workers.ConfirmReady)
  end

  test "a step that finishes after the machine was retired leaves it retired" do
    machine = WalletBench.request_machine!(@name, "H05", authorize?: false)
    Oban.drain_queue(queue: :sprites)
    created = WalletBench.get_machine!(machine.id, authorize?: false)
    assert created.state == :created

    Req.Test.stub(__MODULE__, fn
      %{method: "DELETE"} = conn -> Plug.Conn.send_resp(conn, 204, "")
      conn -> sprites(conn)
    end)

    WalletBench.retire_machine!(created, "test", authorize?: false)

    assert {:error, _stale} =
             created
             |> Ash.Changeset.for_update(:build_baseline, %{})
             |> Ash.update(authorize?: false)

    drain()

    assert WalletBench.get_machine!(machine.id, authorize?: false).state == :retired
  end

  defp drain(opts \\ []) do
    Oban.drain_queue([queue: :sprites, with_recursion: true] ++ opts)
  end

  # The build starts, waits while it runs, then finishes and is checkpointed;
  # the restore waits a minute after the checkpoint, then the chain runs up to
  # readiness.
  defp build(machine) do
    drain()
    assert Process.get(:baseline) == "running"
    Process.put(:baseline, "exit 0")
    Oban.drain_queue(queue: :sprites, with_scheduled: true)
    drain()
    assert WalletBench.get_machine!(machine.id, authorize?: false).state == :checkpointed
    backdate(machine, :updated_at, 61)
    Oban.drain_queue(queue: :sprites, with_scheduled: true)
    drain()
  end

  # Readiness counts 30 seconds from when the boot id was noted.
  defp settle(machine), do: backdate(machine, :boot_seen_at, 31)

  defp backdate(machine, field, seconds) do
    {:ok, id} = Ecto.UUID.dump(machine.id)
    at = DateTime.add(DateTime.utc_now(), -seconds)

    {1, _} =
      Repo.update_all(from(m in "wallet_bench_machines", where: m.id == ^id), set: [{field, at}])
  end

  # A stand-in for the Sprites API, enough for one machine's steps.
  defp sprites(conn) do
    case {conn.method, conn.request_path} do
      {"POST", "/v1/sprites"} ->
        conn |> Plug.Conn.put_status(201) |> Req.Test.json(sprite())

      {"GET", "/v1/sprites/" <> @name} ->
        Req.Test.json(conn, sprite())

      {"GET", "/v1/sprites/" <> @name <> "/checkpoints"} ->
        Req.Test.json(conn, checkpoints())

      {"POST", "/v1/sprites/" <> @name <> "/checkpoint"} ->
        {:ok, body, conn} = Plug.Conn.read_body(conn)
        Process.put(:comment, Jason.decode!(body)["comment"])
        ndjson(conn)

      {"POST", "/v1/sprites/" <> @name <> "/checkpoints/v2/restore"} ->
        ndjson(conn)

      {"POST", "/v1/sprites/" <> @name <> "/exec"} ->
        exec(conn)
    end
  end

  defp exec(conn) do
    argv = for {"cmd", value} <- URI.query_decoder(conn.query_string), do: value

    case argv do
      ["base64", "-w0", "--", "/proc/sys/kernel/random/boot_id"] ->
        [boot_id | _rest] = Process.get(:boot_ids)
        frames(conn, Base.encode64(boot_id <> "\n"))

      ["base64", "-w0", "--", "/tmp/techtree-readiness"] ->
        frames(conn, Base.encode64(Process.get(:upload)))

      ["sh", "-c", _script, "sh", "/tmp/techtree-readiness", "600"] ->
        {:ok, body, conn} = Plug.Conn.read_body(conn)
        Process.put(:upload, body)
        frames(conn, "")

      ["sh", "-c", _script, "/work/bin/machine/job.sh", "baseline"] ->
        frames(conn, Process.get(:baseline) <> "\n")

      ["bash", "-c", "install -d -m 700 /work" <> _rest] ->
        frames(conn, "")

      ["bash", "/work/bin/machine/job.sh", "start", "baseline" | _script] ->
        Process.put(:baseline, "running")
        frames(conn, "started\n")

      ["cat", "/work/baseline/manifest.json"] ->
        frames(
          conn,
          Jason.encode!(%{harness_id: "H05", harness_version: "2.1.286 (Claude Code)"})
        )

      ["bash", "-c", "cd /work/bin && find" <> _rest] ->
        frames(conn, "digest-1  -\n")

      ["bash", "/work/bin/machine/readiness.sh", "H05"] ->
        account = %{
          work_readable: false,
          sudo: false,
          checkpoints_listable: false,
          socket_reachable: false
        }

        frames(conn, Jason.encode!(%{account: account, harness_version: "2.1.286 (Claude Code)"}))
    end
  end

  defp frames(conn, ""), do: Plug.Conn.send_resp(conn, 200, <<3, 0>>)
  defp frames(conn, stdout), do: Plug.Conn.send_resp(conn, 200, <<1>> <> stdout <> <<3, 0>>)

  defp ndjson(conn) do
    Plug.Conn.send_resp(
      conn,
      200,
      Jason.encode!(%{"type" => "complete", "data" => "done"}) <> "\n"
    )
  end

  defp sprite do
    %{
      "id" => "sprite-0123",
      "name" => @name,
      "status" => "running",
      "version" => "0.0.1-rc48",
      "url" => "https://#{@name}.sprites.app",
      "environment_version" => nil
    }
  end

  defp checkpoints do
    current = %{"id" => "Current", "create_time" => "2026-10-04T17:55:48Z", "is_auto" => false}

    case Process.get(:comment) do
      nil ->
        [current]

      comment ->
        made = %{
          "id" => "v2",
          "create_time" => "2026-10-04T17:51:04Z",
          "comment" => comment,
          "is_auto" => false
        }

        [current, made]
    end
  end
end
