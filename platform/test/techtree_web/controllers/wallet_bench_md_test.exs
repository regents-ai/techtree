defmodule TechtreeWeb.WalletBenchMDTest do
  @moduledoc """
  `/wallet-bench.md` gives agents the same score grids as the page, each score
  linked to its result.
  """

  use TechtreeWeb.ConnCase, async: false

  alias Techtree.WalletBenchFixture

  test "both grids, with each score linked to its result", %{conn: conn} do
    tests = WalletBenchFixture.seed!()
    markdown = conn |> get(~p"/wallet-bench.md") |> response(200)

    [_intro, wallet, install] = String.split(markdown, ~r/^## (Wallet|Install)$/m)

    hermes = fn grid ->
      grid |> String.split("\n") |> Enum.find(&String.starts_with?(&1, "| Hermes Agent |"))
    end

    assert hermes.(wallet) =~
             "| Hermes Agent | 1m | 10.0 | [10.0](#{url(~p"/wallet-bench/#{tests.passed.id}")}) | - | - | - | N/A |"

    assert hermes.(install) =~
             "| Hermes Agent | 1m | 9.1 | [10.0](#{url(~p"/wallet-bench/#{tests.passed.id}")}) | - | [8.2](#{url(~p"/wallet-bench/#{tests.failed.id}")}) |"
  end
end
