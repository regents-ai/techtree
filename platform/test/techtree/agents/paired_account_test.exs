defmodule Techtree.Agents.PairedAccountTest do
  use Techtree.DataCase, async: true

  test "the check-in names no account for a person Techtree has not seen" do
    assert Techtree.Agents.PairedAccount.account("did:privy:nobody-here") == nil
  end
end
