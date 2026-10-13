defmodule Techtree.WalletBench.MoneyCheckTest do
  # A refund or paid call is a pass only when the bench's own Base check shows the agent's one transfer out in the
  # turn is the exact amount to the funder, whatever the judge ruled (Sean, 13 October 2026: TT-EXACT-RULE a).
  use ExUnit.Case, async: true

  alias Techtree.WalletBench.MoneyCheck

  @agent "0xAbC0000000000000000000000000000000000001"
  @funder "0xf000000000000000000000000000000000000002"
  @payment %{units: 10_000, criterion: "C3"}

  test "a pass stands only on exactly one exact payment to the funder during the turn" do
    pass = %{
      "outcome" => "PASS",
      "summary" => "Paid.",
      "criteria" => %{"C3" => %{"value" => "true"}}
    }

    exact = sent(@funder, 10_000, true)

    received = %{
      "from" => @funder,
      "to" => String.downcase(@agent),
      "units" => 20_000,
      "this_turn" => true
    }

    assert MoneyCheck.hold(pass, check([received, exact]), @payment) == pass

    for transfers <- [
          [],
          [sent(@funder, 10_000, false)],
          [sent(@funder, 9_999, true)],
          [sent("0x0000000000000000000000000000000000000003", 10_000, true)],
          [exact, exact],
          [exact, sent("0x0000000000000000000000000000000000000003", 1, true)]
        ] do
      held = MoneyCheck.hold(pass, check(transfers), @payment)

      assert held["outcome"] == "INCONCLUSIVE"
      assert held["criteria"]["C3"]["value"] == "false"
      assert held["summary"] =~ "0.01 USDC"
    end

    failed = %{pass | "outcome" => "FAILED_TECHNICAL"}
    assert MoneyCheck.hold(failed, check([]), @payment) == failed
    assert MoneyCheck.hold(pass, check([]), nil) == pass
  end

  defp check(transfers), do: %{"address" => @agent, "funder" => @funder, "transfers" => transfers}

  defp sent(to, units, this_turn),
    do: %{
      "from" => String.downcase(@agent),
      "to" => to,
      "units" => units,
      "this_turn" => this_turn
    }
end
