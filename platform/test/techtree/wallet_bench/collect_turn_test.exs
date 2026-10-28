defmodule Techtree.WalletBench.CollectTurnTest do
  # A downloaded turn folder checks with `sha256sum -c SHA256SUMS`: the site
  # writes the sums of the files as stored, after blanking, and the sums are
  # not blanked themselves (review of 27 Oct: every machine-made sums line read
  # as a blanked 32-byte hex value, and described the bytes before blanking).
  use Techtree.DataCase, async: false

  alias Techtree.WalletBench.{Attempt, Catalog, Evidence, Machine, Turn}

  @name "wb-test-collect"
  @address "0xf6ca0D12952504075664BD5fa3ea98511f482eEa"
  @key "0x" <> String.duplicate("1f", 32)

  setup do
    sprites = Application.get_env(:regent_sprites, :req_options)
    evidence = Application.get_env(:techtree, Evidence)
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

    Req.Test.stub(__MODULE__.Sprites, &sprites/1)
    Req.Test.stub(__MODULE__.Evidence, &store/1)

    on_exit(fn ->
      Application.delete_env(:regent_sprites, :token)
      Application.put_env(:techtree, Evidence, evidence)

      if sprites,
        do: Application.put_env(:regent_sprites, :req_options, sprites),
        else: Application.delete_env(:regent_sprites, :req_options)
    end)
  end

  test "a collected turn stores the sums of its blanked files, and replaces sums the turn left" do
    turn = running_turn!()

    Process.put(:folder, %{
      "stream.jsonl" => ~s({"out": "key #{@key} sent from #{@address}"}\n),
      "turn-summary.json" => ~s({"session_id": "session-1"}),
      "exit_code" => "0\n",
      "start_utc" => "2026-10-27T09:00:00.000Z\n",
      "end_utc" => "2026-10-27T09:01:00.000Z\n",
      "wall_seconds" => "60.000\n",
      "model-calls.jsonl" => "",
      "SHA256SUMS" => String.duplicate("ab", 32) <> "  stream.jsonl\n"
    })

    collected =
      turn
      |> Ash.Changeset.for_update(:collect, %{})
      |> Ash.update!(authorize?: false)

    stored = Process.get(:stored)
    folder = "attempts/#{turn.attempt_id}/#{Catalog.turn_name(turn.test)}/"
    stored = Map.new(stored, fn {key, body} -> {String.replace_prefix(key, folder, ""), body} end)

    assert stored["stream.jsonl"] =~ "[redacted: 32-byte hex value: a private key or a hash]"
    assert stored["stream.jsonl"] =~ @address

    sums =
      for {file, body} <- Enum.sort(Map.delete(stored, "SHA256SUMS")),
          into: "",
          do: sha256(body) <> "  " <> file <> "\n"

    assert stored["SHA256SUMS"] == sums
    assert collected.evidence["SHA256SUMS"]["sha256"] == sha256(sums)
    assert Map.keys(collected.evidence) == Map.keys(stored)
  end

  defp running_turn! do
    batch = Ecto.UUID.generate()

    machine =
      Ash.Seed.seed!(Machine, %{batch_id: batch, name: @name, state: :leased, harness_id: "H10"})

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

    Ash.Seed.seed!(Turn, %{
      attempt_id: attempt.id,
      test: :T1a,
      state: :running,
      prompt: "An install test."
    })
  end

  # A stand-in for the machine: the turn has ended, its folder comes back as
  # one archive, and the tested account holds no secret files.
  defp sprites(%{method: "POST", request_path: "/v1/sprites/" <> @name <> "/exec"} = conn) do
    case for({"cmd", value} <- URI.query_decoder(conn.query_string), do: value) do
      ["sh", "-c", _script, "/work/bin/machine/job.sh", _job] ->
        frames(conn, "exit 0\n")

      ["bash", "-c", _archive, "bash", _folder] ->
        frames(conn, archive(Process.get(:folder)))

      ["sudo", "/.sprite/bin/python3", "/work/bin/machine/secrets.py"] ->
        frames(conn, ~s({"files": []}))
    end
  end

  defp store(%{method: "PUT"} = conn) do
    {:ok, body, conn} = Plug.Conn.read_body(conn)
    "/walletbench-evidence/" <> key = URI.decode(conn.request_path)
    Process.put(:stored, Map.put(Process.get(:stored, %{}), key, body))
    Plug.Conn.send_resp(conn, 200, "")
  end

  defp archive(files) do
    path = Path.join(System.tmp_dir!(), "collect-turn-#{System.unique_integer([:positive])}.tgz")

    try do
      entries = for {name, content} <- files, do: {String.to_charlist("./" <> name), content}
      :ok = :erl_tar.create(String.to_charlist(path), entries, [:compressed])
      path |> File.read!() |> Base.encode64()
    after
      File.rm(path)
    end
  end

  defp frames(conn, stdout), do: Plug.Conn.send_resp(conn, 200, <<1>> <> stdout <> <<3, 0>>)

  defp sha256(body), do: :crypto.hash(:sha256, body) |> Base.encode16(case: :lower)
end
