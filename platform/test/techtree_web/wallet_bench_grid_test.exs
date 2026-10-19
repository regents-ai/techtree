defmodule TechtreeWeb.WalletBenchGridTest do
  @moduledoc """
  The score grid's rows, columns and boxes, from recorded tests.
  """

  use Techtree.DataCase, async: true
  use ExUnitProperties

  alias Techtree.WalletBench
  alias Techtree.WalletBench.Catalog
  alias Techtree.WalletBenchFixture
  alias TechtreeWeb.WalletBenchCopy, as: Copy

  setup do
    WalletBenchFixture.seed!()
    %{attempts: WalletBench.list_attempts!(load: [:turns])}
  end

  test "the wallet grid: a row per agent asked the wallet question, every tool a column", %{
    attempts: attempts
  } do
    grid = Copy.grid(attempts, :wallet)

    assert length(grid.wallets) == length(Catalog.wallet_ids())
    assert length(grid.rows) == Enum.count(Catalog.harness_ids(), &(:T2 in Catalog.tests(&1)))

    # The tools that run come first; a tool that never runs is N/A in every row.
    {running, fixed} = Enum.split_with(grid.wallets, &is_nil(&1.fixed))
    assert grid.wallets == running ++ fixed

    for row <- grid.rows, {cell, wallet} <- Enum.zip(row.cells, grid.wallets), wallet.fixed do
      assert cell == {:fixed, wallet.fixed.reason}
    end

    # Hermes Agent has the only result, so it leads, with its time and mean.
    [hermes | others] = grid.rows
    assert %{agent: "Hermes Agent", overall: 9.0, speed: 61.2} = hermes
    assert Enum.all?(others, &(&1.overall == nil and &1.speed == nil))
    assert others == Enum.sort_by(others, & &1.agent)

    assert [{:result, %{score: 9}}, :not_run, :not_run | _rest] = hermes.cells
  end

  test "the install grid takes the failed install's own count", %{attempts: attempts} do
    [hermes | _others] = Copy.grid(attempts, :install).rows

    # Bankr passed, Foundry Cast is still running, MoonPay's install did not work.
    assert [{:result, %{score: 9}}, :not_run, {:result, %{score: 7}} | _rest] = hermes.cells
    assert hermes.overall == 8.0
  end

  property "a score counts the checks met, and a higher score is never shaded lighter" do
    check all(values <- list_of(member_of(~w(true false open)), length: 9)) do
      criteria =
        values |> Enum.with_index(1) |> Map.new(fn {v, i} -> {"C#{i}", %{"value" => v}} end)

      score = Copy.score(%{"criteria" => criteria})

      assert score == Enum.count(values, &(&1 == "true"))
      assert Copy.shade(score) >= Copy.shade(max(score - 1, 0))
    end
  end
end
