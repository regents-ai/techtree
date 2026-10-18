defmodule TechtreeWeb.OutageTest do
  use Techtree.DataCase, async: true

  alias TechtreeWeb.Outage

  test "hands back what the reads return" do
    assert Outage.read(fn -> :read end) == {:ok, :read}
  end

  test "with the database answering, a failing read is raised again unchanged" do
    assert_raise DBConnection.ConnectionError, "a connection the page lost", fn ->
      Outage.read(fn -> raise DBConnection.ConnectionError, "a connection the page lost" end)
    end
  end
end
