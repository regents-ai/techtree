defmodule TechtreeWeb.OutageTest do
  use Techtree.DataCase, async: true

  alias TechtreeWeb.Outage

  test "hands back what the reads return" do
    assert Outage.read(fn -> :read end) == {:ok, :read}
  end

  # Right after a restart the database answers again, but each pooled connection
  # still fails once before the pool replaces it.
  test "a lost connection gives the outage note even while the database answers" do
    log =
      ExUnit.CaptureLog.capture_log(fn ->
        assert :database_down =
                 Outage.read(fn -> raise DBConnection.ConnectionError, "connection closed" end)
      end)

    # The outage signal operators search for in the logs.
    assert log =~ "Database connection lost; page shows its outage note: connection closed"
  end

  test "a failure that isn't a lost connection is raised again unchanged" do
    assert_raise ArgumentError, "a bug in the page", fn ->
      Outage.read(fn -> raise ArgumentError, "a bug in the page" end)
    end
  end
end
