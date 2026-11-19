defmodule Techtree.WalletBench.GiveUpTest do
  # A step that runs out of retries stores why in plain words on the public
  # pages, and its error's own text only in the log (attempt a08fdc5c, 19 Nov
  # 2026: the judge's key was refused and the test's page showed the raw Ash
  # error, module names and a stack line). A reason the bench wrote itself is
  # stored as written.
  use Techtree.DataCase, async: false
  use Oban.Testing, repo: Techtree.Repo

  import ExUnit.CaptureLog

  alias Techtree.WalletBench
  alias Techtree.WalletBench.{Attempt, Catalog, Evidence, Machine, Turn}

  @refusal %RegentAnthropic.Error{
    reason: {:anthropic, 401, "authentication_error", "invalid x-api-key"}
  }

  @files %{
    "transcript.md" => "The agent installed the wallet.\n",
    "verify-install.txt" => "installed 1.2.3\n",
    "verify-storage.txt" => "no plain secrets\n"
  }

  defmodule Refusing do
    # The judge's model provider refusing the bench's key, as Anthropic answers it.
    @behaviour RegentHttp

    @impl true
    def request(_opts) do
      {:ok,
       Req.Response.new(
         status: 401,
         body: %{
           "type" => "error",
           "error" => %{"type" => "authentication_error", "message" => "invalid x-api-key"}
         }
       )}
    end
  end

  setup do
    previous = %{
      anthropic: Application.get_env(:regent_anthropic, :api_key),
      client: Application.get_env(:regent_http, :client),
      evidence: Application.get_env(:techtree, Evidence),
      sprites: Application.get_env(:regent_sprites, :req_options)
    }

    Application.put_env(:regent_anthropic, :api_key, "test-anthropic-key")
    Application.put_env(:regent_http, :client, Refusing)
    Application.put_env(:regent_sprites, :token, "test-sprites-token")
    Application.put_env(:regent_sprites, :req_options, plug: {Req.Test, __MODULE__.Sprites})

    Application.put_env(:techtree, Evidence,
      endpoint: "https://evidence.example",
      bucket: "walletbench-evidence",
      region: "auto",
      access_key_id: "test-access-key",
      secret_access_key: "test-secret-key",
      req_options: [plug: {Req.Test, __MODULE__.Evidence}]
    )

    Req.Test.stub(__MODULE__.Evidence, &stored/1)
    Req.Test.stub(__MODULE__.Sprites, &unavailable/1)

    on_exit(fn ->
      restore(:regent_anthropic, :api_key, previous.anthropic)
      restore(:regent_http, :client, previous.client)
      restore(:techtree, Evidence, previous.evidence)
      restore(:regent_sprites, :req_options, previous.sprites)
      Application.delete_env(:regent_sprites, :token)
    end)
  end

  test "a judge whose provider refused the bench stores a plain reason, and the error's text only in the log" do
    {attempt, turn} = finished_turn!()
    AshOban.run_trigger(turn, :judge)

    log =
      capture_log(fn ->
        Oban.drain_queue(queue: :wallet_bench_judge, with_scheduled: true, with_recursion: true)
      end)

    # The rows as the job left them, read with no actor.
    assert %Turn{state: :failed, failure: failure} = Ash.get!(Turn, turn.id, authorize?: false)
    refute failure == Exception.message(@refusal)

    for raw <- [
          Exception.message(@refusal),
          "invalid x-api-key",
          "authentication_error",
          "401",
          "Bread Crumbs",
          "RegentAnthropic",
          "Techtree.",
          "Ash.",
          "** (",
          ".ex:"
        ] do
      refute failure =~ raw
    end

    # The attempt stops with the turn's reason as written, and both timelines
    # carry that same reason.
    attempt = Ash.get!(Attempt, attempt.id, authorize?: false)
    assert attempt.failure == Catalog.turn_name(:T1a) <> ": " <> failure

    details =
      for event <- WalletBench.list_attempt_events!(attempt.id, authorize?: false),
          event.detail["failure"],
          do: event.detail["failure"]

    assert details == [failure, attempt.failure]

    # The provider's own words reach the log once for the give-up, not once per try.
    assert [_once] = Regex.scan(~r/invalid x-api-key/, log)
  end

  test "a machine step whose provider was unavailable stores a plain reason" do
    machine =
      WalletBench.request_machine!("wb-test-give-up", "H05",
        authorize?: false,
        actor: %Techtree.Actors.Operator{name: "test-operator"}
      )

    capture_log(fn ->
      Oban.drain_queue(queue: :sprites, with_scheduled: true, with_recursion: true)
    end)

    failed = WalletBench.get_machine!(machine.id, authorize?: false)
    assert failed.state == :failed

    raw = Exception.message(%RegentSprites.Error{reason: {:sprites, 503, "capacity"}})
    refute failed.failure =~ raw
    refute failed.failure =~ "503"
    refute failed.failure =~ "capacity"
    refute failed.failure =~ "Sprites"

    assert [%{detail: %{"failure" => detail}}] =
             machine.id
             |> WalletBench.list_machine_events!(authorize?: false)
             |> Enum.filter(&(&1.step == :failed))

    assert detail == failed.failure
  end

  test "a reason the bench wrote itself is stored as written" do
    {attempt, turn} = finished_turn!()
    reason = "The turn's archive holds two files with the same name."

    turn
    |> Ash.Changeset.for_update(:mark_failed, %{error: reason})
    |> Ash.update!(authorize?: false)

    assert Ash.get!(Turn, turn.id, authorize?: false).failure == reason

    assert Ash.get!(Attempt, attempt.id, authorize?: false).failure ==
             Catalog.turn_name(:T1a) <> ": " <> reason
  end

  defp finished_turn! do
    batch = Ecto.UUID.generate()

    machine =
      Ash.Seed.seed!(Machine, %{
        batch_id: batch,
        name: "wb-test-give-up-#{String.slice(batch, 0, 8)}",
        state: :leased,
        harness_id: "H10",
        manifest: %{
          "harness_version" => "0.1.0",
          "model" => "test-model",
          "reasoning_effort" => "high",
          "translator" => "test-translator",
          "os" => "Ubuntu 24.04"
        }
      })

    attempt =
      Ash.Seed.seed!(Attempt, %{
        batch_id: batch,
        replicate: 1,
        harness_id: "H10",
        wallet_id: "W03",
        state: :testing,
        plan: :wallet,
        machine_id: machine.id
      })

    turn =
      Ash.Seed.seed!(Turn, %{
        attempt_id: attempt.id,
        test: :T1a,
        state: :finished,
        prompt: "An install test.",
        exit_code: 0,
        evidence:
          Map.new(@files, fn {file, body} ->
            {file, %{"sha256" => sha256(body), "bytes" => byte_size(body)}}
          end)
      })

    {attempt, turn}
  end

  defp stored(%{method: "GET"} = conn) do
    file = conn.request_path |> URI.decode() |> Path.basename()
    Plug.Conn.send_resp(conn, 200, Map.fetch!(@files, file))
  end

  defp unavailable(conn) do
    conn |> Plug.Conn.put_status(503) |> Req.Test.json(%{"error" => "capacity"})
  end

  defp restore(app, key, nil), do: Application.delete_env(app, key)
  defp restore(app, key, value), do: Application.put_env(app, key, value)

  defp sha256(body), do: :crypto.hash(:sha256, body) |> Base.encode16(case: :lower)
end
