defmodule Techtree.AgentsTest do
  use Techtree.DataCase, async: true

  test "the check-in names no account for a person Techtree has not seen" do
    assert Techtree.Agents.account("did:privy:nobody-here") == nil
  end
end
