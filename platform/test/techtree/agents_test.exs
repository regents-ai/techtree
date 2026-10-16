defmodule Techtree.AgentsTest do
  use Techtree.DataCase, async: true

  test "a person with no account on this site gives the check-in no account" do
    assert Techtree.Agents.account("did:privy:nobody-here") == nil
  end
end
