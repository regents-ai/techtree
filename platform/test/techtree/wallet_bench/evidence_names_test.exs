defmodule Techtree.WalletBench.EvidenceNamesTest do
  @moduledoc """
  A file a turn recorded keeps its name only when that name is one single,
  harmless file wherever a download is unpacked.
  """
  use ExUnit.Case, async: true
  use ExUnitProperties

  alias Techtree.WalletBench.Evidence

  test "names the bench writes, and an agent's own picture, are kept" do
    for name <-
          ~w(session.jsonl install.log turn-summary.json exit_code model-calls.jsonl) ++
            ["self portrait.png"] do
      assert Evidence.file_name?(name), name
    end
  end

  test "a name that could reach outside its folder or break on unpacking is refused" do
    for name <- [
          ".",
          "..",
          "",
          "a\\b",
          "..\\..\\x",
          "a/b",
          "C:x",
          "nul\0",
          "tab\tname",
          "what?",
          "a|b",
          String.duplicate("a", 129)
        ] do
      refute Evidence.file_name?(name), inspect(name)
    end
  end

  property "no kept name holds a path separator or a control character" do
    check all(name <- string(:printable, min_length: 1, max_length: 140)) do
      if Evidence.file_name?(name) do
        refute name =~ ~r{[/\\\x00-\x1f]}
        refute name in [".", ".."]
      end
    end
  end
end
