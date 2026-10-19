defmodule TechtreeWeb.WalletBenchEvidenceController do
  @moduledoc """
  One recorded file of a wallet test: an image the agent saved as that image,
  when its own bytes say it is one of that kind, and everything else as plain
  text.

  Only a file the turn recorded is served: the turn and file names are looked
  up in the turn's own list, never used as a path, and the bytes read back
  must match the fingerprint recorded with them (`Techtree.WalletBench.Evidence.recorded/2`).
  Everything stored was blanked before it was stored (`Techtree.WalletBench.Blank`).
  """

  use TechtreeWeb, :controller

  alias Techtree.WalletBench
  alias Techtree.WalletBench.{Catalog, Evidence}
  alias TechtreeWeb.WalletBenchCopy, as: Copy

  @load [:machine, :turns, :payments, :model_spend_usd, :judge_cost_usd]

  # The type is one of four fixed values, chosen from the stored file's own header and never from the request; an
  # image or plain text runs no script, and the site sends nosniff and its CSP with every answer. A file is held
  # whole while it is sent, so it takes one of the machine's download places like a zip.
  # sobelow_skip ["XSS.ContentType", "XSS.SendResp"]
  def show(conn, %{"id" => id, "turn" => turn_name, "file" => file}) do
    with {:ok, id} <- Ecto.UUID.cast(id),
         {:ok, attempt} <- WalletBench.get_attempt(id, load: [:turns]),
         %{evidence: %{^file => _recorded}} = turn <-
           Enum.find(attempt.turns, &(Catalog.turn_name(&1.test) == turn_name)) do
      with_download_place(conn, fn ->
        {:ok, body} = Evidence.recorded(turn, file)

        conn
        |> put_resp_content_type(content_type(file, body), nil)
        |> send_resp(200, body)
      end)
    else
      _missing -> raise TechtreeWeb.NotFoundError, "no recorded file has that name"
    end
  end

  # Downloads this machine sends at once; one more is asked to try again.
  @downloads 4

  @doc """
  The whole test as one zip, written as it is sent: `results.json`, the test's
  page in the bench's own record and words, then every file each test
  recorded, under its test's name.

  Before anything is sent, every file is read through once and its size and
  sha256 checked against the turn's record, so a stored file that changed gets
  the error page, not a broken download. The zip then reads the files one at a
  time, checking each again, so a download holds one file in memory at most;
  a file that changes between the two reads ends the connection before any of
  its bytes go out. At most #{@downloads} downloads, zips and single files
  together, are sent at once on a machine; another gets a page asking to try
  again.
  """
  def results(conn, %{"id" => id}) do
    with {:ok, id} <- Ecto.UUID.cast(id),
         {:ok, attempt} <- WalletBench.get_attempt(id, load: @load) do
      with_download_place(conn, fn -> send_results(conn, attempt) end)
    else
      _missing -> raise TechtreeWeb.NotFoundError, "no wallet test has that number"
    end
  end

  # Each download holds a place while it is sent, given back when it ends; a
  # process that dies gives its place back with it.
  defp with_download_place(conn, send) do
    {:ok, _owner} = Registry.register(TechtreeWeb.ResultsDownloads, :download, nil)

    if Registry.count_match(TechtreeWeb.ResultsDownloads, :download, :_) > @downloads do
      Registry.unregister(TechtreeWeb.ResultsDownloads, :download)
      busy(conn)
    else
      try do
        send.()
      after
        Registry.unregister(TechtreeWeb.ResultsDownloads, :download)
      end
    end
  end

  defp busy(conn) do
    conn
    |> put_resp_header("retry-after", "30")
    |> put_status(503)
    |> put_root_layout(false)
    |> put_view(html: TechtreeWeb.ErrorHTML)
    |> render(:"503")
  end

  defp send_results(conn, attempt) do
    files =
      for turn <- attempt.turns,
          file <- Enum.sort(Map.keys(turn.evidence || %{})),
          do: {turn, file}

    for {turn, file} <- files do
      with {:error, reason} <- Evidence.check(turn, file),
           do: raise(TechtreeWeb.ResultsUnreadableError, inspect(reason))
    end

    folder = "wallet-test-#{String.slice(attempt.id, 0, 8)}"
    mtime = attempt.inserted_at

    entries =
      for {turn, file} <- files do
        Zstream.entry(
          "#{folder}/#{Catalog.turn_name(turn.test)}/#{file}",
          Stream.map([file], &recorded!(turn, &1)),
          mtime: mtime
        )
      end

    results =
      Zstream.entry("#{folder}/results.json", [Jason.encode!(summary(attempt), pretty: true)],
        mtime: mtime
      )

    conn
    |> put_resp_header("content-disposition", ~s(attachment; filename="#{folder}.zip"))
    |> put_resp_content_type("application/zip", nil)
    |> send_chunked(200)
    |> send_stream(Zstream.zip([results | entries]))
  end

  # Each piece goes out as it is made; a connection that closes or fails stops the rest.
  defp send_stream(conn, stream) do
    Enum.reduce_while(stream, conn, fn data, conn ->
      case chunk(conn, data) do
        {:ok, conn} -> {:cont, conn}
        {:error, _gone} -> {:halt, conn}
      end
    end)
  end

  defp recorded!(turn, file) do
    case Evidence.recorded(turn, file) do
      {:ok, body} -> body
      {:error, reason} -> raise "A recorded file can't be read: #{inspect(reason)}"
    end
  end

  # What the test's page shows, field by field: every value is named here, so
  # nothing else the bench keeps on a test can reach the download.
  defp summary(attempt) do
    %{
      page: url(~p"/wallet-bench/#{attempt.id}"),
      agent: Catalog.harness!(attempt.harness_id).name,
      wallet_tool: Catalog.wallet!(attempt.wallet_id).name,
      status: Copy.status(attempt.state),
      started_at: attempt.inserted_at,
      failure: attempt.failure,
      machine:
        attempt.machine &&
          Map.take(attempt.machine.manifest, ~w(harness_version model reasoning_effort os)),
      agent_address: attempt.agent_address,
      model_cost_usd: attempt.model_spend_usd,
      judge_cost_usd: attempt.judge_cost_usd,
      tests: Enum.map(attempt.turns, &turn_summary/1),
      funding:
        for payment <- attempt.payments do
          %{
            sent: Copy.payment(payment),
            state: Copy.payment_state(payment.state),
            transaction: payment.hash
          }
        end
    }
  end

  defp turn_summary(turn) do
    %{
      test: Copy.test(turn.test),
      folder: Catalog.turn_name(turn.test),
      state: Copy.turn_state(turn.state),
      prompt: turn.prompt,
      started_at: turn.started_at,
      ended_at: turn.ended_at,
      seconds: turn.wall_seconds,
      model_cost_usd: turn.model_spend_usd,
      judge_cost_usd: turn.judge_cost_usd,
      failure: turn.failure,
      ruling: turn.judgment && ruling(turn),
      version_installed: turn.checks["version"] && Copy.version(turn.checks["version"]),
      base_check: Copy.base(turn.checks["base"]) || Copy.money(turn.checks["money"]),
      files:
        Map.new(turn.evidence || %{}, fn {file, recorded} ->
          {file, Map.take(recorded, ~w(bytes sha256))}
        end)
    }
  end

  defp ruling(%{judgment: judgment} = turn) do
    %{
      outcome: Copy.outcome(judgment),
      judged_by: judgment["model"],
      summary: judgment["summary"],
      reasoning: judgment["reasoning"],
      checks:
        for {id, check} <- Enum.sort(judgment["criteria"] || %{}) do
          %{
            check: Copy.criterion_question(turn.test, id),
            answer: Copy.criterion(check["value"]),
            why: check["reason"]
          }
        end
    }
  end

  # The same headers the machine's image_type.py reads.
  defp content_type(file, body) do
    case {Path.extname(file), body} do
      {".png", <<0x89, "PNG\r\n", 0x1A, "\n", _rest::binary>>} -> "image/png"
      {ext, <<0xFF, 0xD8, _rest::binary>>} when ext in [".jpg", ".jpeg"] -> "image/jpeg"
      {".webp", <<"RIFF", _size::binary-size(4), "WEBP", _rest::binary>>} -> "image/webp"
      _text -> "text/plain; charset=utf-8"
    end
  end
end
