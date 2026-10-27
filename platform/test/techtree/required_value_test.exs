defmodule Techtree.RequiredValueTest do
  # Regression: the shared ash_required helper in public was version 6, which runs
  # with an empty search path and cannot find ash_raise_error, so a missing required
  # value raised "function does not exist" instead of Ash's error. On a fresh
  # database the Credits library's first migration installed that copy again after
  # the site's version 7.

  use ExUnit.Case, async: true

  setup do
    owner = Ecto.Adapters.SQL.Sandbox.start_owner!(Techtree.Repo)
    on_exit(fn -> Ecto.Adapters.SQL.Sandbox.stop_owner(owner) end)
  end

  test "a missing required value raises Ash's error, and a present one comes back" do
    query = "SELECT public.ash_required($1::text, '{\"field\": \"title\"}'::jsonb)"

    assert %{rows: [["kept"]]} = Ecto.Adapters.SQL.query!(Techtree.Repo, query, ["kept"])

    assert {:error, %Postgrex.Error{postgres: %{message: "ash_error: " <> payload}}} =
             Ecto.Adapters.SQL.query(Techtree.Repo, query, [nil])

    assert Jason.decode!(payload) == %{"field" => "title"}
  end
end
