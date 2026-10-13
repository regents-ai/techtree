defmodule TechtreeWeb.WalletBenchMD do
  @moduledoc """
  The Wallet Bench as Markdown, for agents reading `/wallet-bench.md`: the
  same answer and the same short list the page shows, in the page's words
  (`TechtreeWeb.WalletBenchCopy`). Every value is the bench's own (catalogue
  names, states and rulings), so nothing in it was written by a visitor.
  """

  use TechtreeWeb, :verified_routes

  alias TechtreeWeb.WalletBenchCopy, as: Copy

  @doc "The answer grid, then every attempt that is running or has a result, newest first."
  @spec render([map()], DateTime.t()) :: String.t()
  def render(attempts, generated_at) do
    answer = Copy.answer(attempts)
    listed = Enum.filter(attempts, &Copy.settled_or_running?/1)

    """
    # Wallet Bench

    Which coding agent can set up and use which wallet tool, from Techtree's
    AgentWalletBench. The same results as #{url(~p"/wallet-bench")}.

    ## Which agent works with which wallet

    Each box is the pair's newest judged wallet test, linked to it.

    #{grid(answer)}

    ## Every test with a result

    Newest first, with tests still running.#{left_out(length(attempts) - length(listed))}

    #{list(listed)}

    Read at #{DateTime.to_iso8601(generated_at)}.
    """
  end

  defp grid(%{wallets: wallets, rows: rows}) do
    header = row(["Agent" | wallets])
    rule = row(Enum.map(["Agent" | wallets], fn _column -> "---" end))

    body =
      Enum.map(rows, fn %{agent: agent, cells: cells} ->
        row([agent | Enum.map(cells, &cell/1)])
      end)

    Enum.join([header, rule | body], "\n")
  end

  defp left_out(0), do: ""
  defp left_out(1), do: " One test with no result is left out."
  defp left_out(count), do: " #{count} tests with no result are left out."

  defp cell(nil), do: "Not yet"

  defp cell(%{attempt: attempt, ruling: ruling}),
    do: "[#{Copy.verdict(ruling)}](#{url(~p"/wallet-bench/#{attempt.id}")})"

  defp list([]), do: "No test has a result yet."

  defp list(attempts) do
    columns = ["Agent and wallet", "Started (UTC)", "Status", "Install", "Wallet", "Model cost"]

    body =
      Enum.map(attempts, fn attempt ->
        row([
          "[#{Copy.pair(attempt)}](#{url(~p"/wallet-bench/#{attempt.id}")})",
          Calendar.strftime(attempt.inserted_at, "%Y-%m-%d %H:%M"),
          Copy.status(attempt.state),
          attempt.turns |> Copy.install_result() |> Copy.outcome(),
          wallet(attempt),
          Copy.dollars(attempt.model_spend_usd)
        ])
      end)

    Enum.join([row(columns), row(Enum.map(columns, fn _column -> "---" end)) | body], "\n")
  end

  defp wallet(attempt) do
    words = attempt.turns |> Copy.wallet_result() |> Copy.outcome()
    if Copy.earlier_question?(attempt), do: words <> " (earlier question)", else: words
  end

  # A judge's words (a flagged file's name) stay inside their cell.
  defp row(cells),
    do: "| " <> Enum.map_join(cells, " | ", &String.replace(&1, ["|", "\n", "\r"], " ")) <> " |"
end
