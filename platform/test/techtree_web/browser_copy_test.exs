defmodule TechtreeWeb.BrowserCopyTest do
  @moduledoc """
  The browser tests drop and recreate their own database before each run, by a
  shell command that carries TECHTREE_BROWSER_COPY. A copy that isn't lowercase
  letters, digits and underscores is refused before any command runs.
  """
  use ExUnit.Case, async: true

  @tag :tmp_dir
  test "a copy that could break out of the command is refused, and nothing runs", %{
    tmp_dir: dir
  } do
    ran = Path.join(dir, "command-ran")

    # The installed Playwright, run directly: nothing is fetched.
    assets = Path.expand("../../assets", __DIR__)

    {output, status} =
      System.cmd(Path.join(assets, "node_modules/.bin/playwright"), ["test"],
        cd: assets,
        env: [{"TECHTREE_BROWSER_COPY", "x';touch #{ran};exit 1;'"}],
        stderr_to_stdout: true
      )

    assert status != 0
    assert output =~ "TECHTREE_BROWSER_COPY may hold only lowercase letters"
    refute File.exists?(ran)
  end
end
