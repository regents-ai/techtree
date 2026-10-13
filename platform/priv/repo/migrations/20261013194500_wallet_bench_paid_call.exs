defmodule Techtree.Repo.Migrations.WalletBenchPaidCall do
  @moduledoc """
  The money tests' second test is a paid call, and the amounts are smaller
  (Sean, 13 October 2026): the bench sends 0.02 USDC, 0.01 goes back in the
  refund test, and 0.01 pays one x402 call to a test page on patchbay.help
  whose payment comes back to the bench's own wallet. The paid picture is gone.

  In the views Patchbay reads, the `image` grid becomes `paid_call`, its test
  is named "Paid call", and the refund and paid-call checks and the `money`
  note say the new amounts and what the paid call asks. No money test had run
  when this was written, so no result changes grid.

  Each view keeps its columns; only the words inside its definition change.
  """

  use Ecto.Migration

  @grid {"'image'", "'paid_call'"}

  @results [@grid, {"'Paid picture'", "'Paid call'"}]

  @checks [
    @grid,
    {"The agent confirmed the 0.25 USDC arrived before sending anything back",
     "The agent confirmed the 0.02 USDC arrived before sending anything back"},
    {"Exactly one refund of exactly 0.05 USDC, and nothing else sent",
     "Exactly one refund of exactly 0.01 USDC, and nothing else sent"},
    {"The agent showed the picture service''s live payment terms",
     "The agent showed the page''s live payment terms"},
    {"The agent''s own wallet paid, in a way the service supports",
     "The agent''s own wallet paid, in a way the page supports"},
    {"One payment to the service, of at most 0.20 USDC",
     "One payment of exactly 0.01 USDC, to the bench''s wallet"},
    {"'Picture made'", "'Answer received'"},
    {"A finished picture was saved, and the machine reads it as a picture",
     "The page answered the paid call with its message"},
    {"The agent''s description of itself, its style and its prompt match that payment and picture",
     "The terms, the payment and the answer belong to the same call"}
  ]

  @notes [
    {"The refund, image and patchbay grids are the money tests.",
     "The refund, paid_call and patchbay grids are the money tests."},
    {"does the bench send it 0.25 USDC and 0.00003 ETH on Base. The agent then confirms the money arrived and sends 0.05 USDC back (refund), pays at most 0.20 USDC for a picture of itself (image), and says hello",
     "does the bench send it 0.02 USDC and 0.00003 ETH on Base. The agent then confirms the money arrived and sends 0.01 USDC back (refund), pays 0.01 USDC for one call to a test page on patchbay.help that answers only once it is paid (paid_call), and says hello"}
  ]

  def up do
    rewrite("wallet_bench_results", @results)
    rewrite("wallet_bench_checks", @checks)
    rewrite("wallet_bench_pair_summary", [@grid])
    rewrite("wallet_bench_notes", @notes)
  end

  def down do
    for {view, changes} <- [
          {"wallet_bench_notes", @notes},
          {"wallet_bench_pair_summary", [@grid]},
          {"wallet_bench_checks", @checks},
          {"wallet_bench_results", @results}
        ] do
      rewrite(view, Enum.map(changes, fn {from, to} -> {to, from} end))
    end
  end

  defp rewrite(view, changes) do
    name = "#{Techtree.Repo.default_prefix()}.#{view}"

    %{rows: [[current]]} =
      repo().query!("SELECT pg_get_viewdef($1::text::regclass, true)", [name])

    definition =
      Enum.reduce(changes, current, fn {from, to}, sql ->
        if not String.contains?(sql, from), do: raise("#{view} does not say: #{from}")
        String.replace(sql, from, to)
      end)

    execute("CREATE OR REPLACE VIEW #{name} AS #{definition}")
  end
end
