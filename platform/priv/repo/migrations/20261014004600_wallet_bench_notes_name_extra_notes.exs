defmodule Techtree.Repo.Migrations.WalletBenchNotesNameExtraNotes do
  @moduledoc """
  `wallet_bench_notes` gains one row, `extra_notes`: what an extra note is, in
  the bench's own words, for the heading Patchbay shows over
  `wallet_bench_extra_notes` (asked by Patchbay, 14 October 2026; Patchbay
  keeps no wording of its own for the bench). Every other note is unchanged.
  """

  use Ecto.Migration

  @last "'::text)) n(key, text)"
  @added "'::text), ('extra_notes'::text,'Extra notes are odd things the bench saw about one release of an agent or a wallet tool. A note sits beside every result of that release. It explains a result and never changes one.'::text)) n(key, text)"

  def up, do: rewrite(@last, @added)

  def down, do: rewrite(@added, @last)

  defp rewrite(from, to) do
    name = "#{Techtree.Repo.default_prefix()}.wallet_bench_notes"

    %{rows: [[current]]} =
      repo().query!("SELECT pg_get_viewdef($1::text::regclass, true)", [name])

    if not String.contains?(current, from), do: raise("wallet_bench_notes does not say: #{from}")

    execute("CREATE OR REPLACE VIEW #{name} AS #{String.replace(current, from, to)}")
  end
end
