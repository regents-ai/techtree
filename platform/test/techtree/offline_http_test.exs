defmodule Techtree.OfflineHttpTest do
  @moduledoc "Tests stay on this machine: an outside request fails where it starts."

  use ExUnit.Case, async: true

  test "a request to an outside host raises before it leaves" do
    assert_raise RuntimeError, ~r/tests stay on this machine/, fn ->
      Req.get!("https://mainnet.base.org", retry: false)
    end
  end

  test "a request to this machine goes through as usual" do
    assert {:error, %Req.TransportError{reason: :econnrefused}} =
             Req.get("http://127.0.0.1:9", retry: false)
  end
end
