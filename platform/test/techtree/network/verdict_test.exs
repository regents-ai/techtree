defmodule Techtree.Network.VerdictTest do
  use ExUnit.Case, async: true
  use ExUnitProperties

  alias Techtree.Network.Assessment
  alias Techtree.Network.Verdict

  defp assessment(reason, wins, losses, ties \\ 0) do
    %Assessment{reason: reason, wins: wins, losses: losses, ties: ties}
  end

  test "the five published Results read as their task counts allow" do
    # Wins, ties and losses as the five live Results recorded them.
    assert Verdict.of(assessment(:cleared_rule, 22, 0, 14)) == :improved
    assert Verdict.of(assessment(:cleared_rule, 24, 0, 12)) == :improved
    assert Verdict.of(assessment(:cleared_rule, 2, 0, 4)) == :too_close_to_call
    assert Verdict.of(assessment(:fell_past_rule, 2, 3, 5)) == :too_close_to_call
    assert Verdict.of(assessment(:fell_past_rule, 1, 3, 6)) == :too_close_to_call
  end

  test "the line falls where the exact sign test puts it" do
    # Five tasks all one way is 2/32 by chance, six is 2/64.
    assert Verdict.of(assessment(:cleared_rule, 5, 0)) == :too_close_to_call
    assert Verdict.of(assessment(:cleared_rule, 6, 0)) == :improved
    assert Verdict.of(assessment(:fell_past_rule, 0, 6)) == :regressed
  end

  test "a higher score with more tasks worse is never an improvement" do
    # A few large gains can lift the mean while most tasks get worse.
    assert Verdict.of(assessment(:cleared_rule, 0, 6)) == :too_close_to_call
    assert Verdict.of(assessment(:fell_past_rule, 6, 0)) == :too_close_to_call
  end

  property "a rule the change does not clear is never more than too close to call" do
    check all(
            reason <- member_of([:rose_short_of_rule, :fell_short_of_rule]),
            wins <- integer(0..60),
            losses <- integer(0..60)
          ) do
      assert Verdict.of(assessment(reason, wins, losses)) == :too_close_to_call
    end
  end

  property "swapping better and worse mirrors the verdict" do
    check all(wins <- integer(0..60), losses <- integer(0..60)) do
      mirrored =
        case Verdict.of(assessment(:cleared_rule, wins, losses)) do
          :improved -> :regressed
          :too_close_to_call -> :too_close_to_call
        end

      assert Verdict.of(assessment(:fell_past_rule, losses, wins)) == mirrored
    end
  end

  property "one more task getting better never makes an improvement less sure" do
    check all(wins <- integer(0..60), losses <- integer(0..60)) do
      if Verdict.of(assessment(:cleared_rule, wins, losses)) == :improved do
        assert Verdict.of(assessment(:cleared_rule, wins + 1, losses)) == :improved
      end
    end
  end

  property "ties never change the verdict" do
    check all(
            reason <- member_of([:cleared_rule, :fell_past_rule, :rose_short_of_rule]),
            wins <- integer(0..40),
            losses <- integer(0..40),
            ties <- integer(0..40)
          ) do
      assert Verdict.of(assessment(reason, wins, losses, ties)) ==
               Verdict.of(assessment(reason, wins, losses))
    end
  end
end
