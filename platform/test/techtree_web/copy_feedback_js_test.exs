defmodule TechtreeWeb.CopyFeedbackJSTest do
  use ExUnit.Case, async: true

  test "copy hooks handle overlapping and repeated clipboard attempts" do
    test_file = Path.expand("../js/copy_feedback_test.mjs", __DIR__)

    {output, status} =
      System.cmd("node", ["--test", test_file],
        cd: Path.expand("../..", __DIR__),
        stderr_to_stdout: true
      )

    assert status == 0, output
    assert output =~ "pass 2"
  end
end
