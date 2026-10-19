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
  # image or plain text runs no script, and the site sends nosniff and its CSP with every answer.
  # sobelow_skip ["XSS.ContentType", "XSS.SendResp"]
  def show(conn, %{"id" => id, "turn" => turn_name, "file" => file}) do
    with {:ok, id} <- Ecto.UUID.cast(id),
         {:ok, attempt} <- WalletBench.get_attempt(id, load: [:turns]),
         %{evidence: %{^file => _recorded}} = turn <-
           Enum.find(attempt.turns, &(Catalog.turn_name(&1.test) == turn_name)) do
      {:ok, body} = Evidence.recorded(turn, file)

      conn
      |> put_resp_content_type(content_type(file, body), nil)
      |> send_resp(200, body)
    else
      _missing -> raise TechtreeWeb.NotFoundError, "no recorded file has that name"
    end
  end

  @doc """
  The whole test as one zip: `results.json`, what the test's page shows as the
  bench recorded it, and every file each test recorded, under its test's name.
  Each file is read back through the same fingerprint check as a single file.
  """
  def results(conn, %{"id" => id}) do
    with {:ok, id} <- Ecto.UUID.cast(id),
         {:ok, attempt} <- WalletBench.get_attempt(id, load: @load) do
      folder = "wallet-test-#{String.slice(attempt.id, 0, 8)}"

      files =
        for turn <- attempt.turns, file <- Map.keys(turn.evidence || %{}), do: {turn, file}

      recorded =
        files
        |> Task.async_stream(
          fn {turn, file} ->
            {~c"#{folder}/#{Catalog.turn_name(turn.test)}/#{file}", Evidence.recorded(turn, file)}
          end,
          max_concurrency: 4,
          timeout: :timer.seconds(20)
        )
        |> Enum.map(fn
          {:ok, {name, {:ok, body}}} ->
            {name, body}

          {:ok, {_name, {:error, reason}}} ->
            raise "A recorded file can't be read: #{inspect(reason)}"
        end)

      results =
        {~c"#{folder}/results.json", Jason.encode!(summary(attempt), pretty: true)}

      {:ok, {_name, zip}} = :zip.create(~c"#{folder}.zip", [results | recorded], [:memory])

      conn
      |> put_resp_header("content-disposition", ~s(attachment; filename="#{folder}.zip"))
      |> put_resp_content_type("application/zip", nil)
      |> send_resp(200, zip)
    else
      _missing -> raise TechtreeWeb.NotFoundError, "no wallet test has that number"
    end
  end

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
      tests:
        for turn <- attempt.turns do
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
            ruling: turn.judgment,
            bench_checks: turn.checks,
            files: turn.evidence || %{}
          }
        end,
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
