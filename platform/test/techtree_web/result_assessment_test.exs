defmodule TechtreeWeb.ResultAssessmentTest do
  use ExUnit.Case, async: true

  alias TechtreeWeb.ResultAssessment

  test "a score too small for three places says so, and zero never reads as -0" do
    assert ResultAssessment.reward(0.0004) == "between 0 and 0.001"
    assert ResultAssessment.reward(-0.0004) == "between 0 and -0.001"
    assert ResultAssessment.reward(-0.0) == "0"
    assert ResultAssessment.reward(1 / 3) == "0.333"
    assert ResultAssessment.change(0.0004) == "between 0 and +0.001"
    assert ResultAssessment.change(-0.0) == "0"
  end
end
