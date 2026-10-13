defmodule Techtree.LocalDatabaseFixture do
  @moduledoc false

  # The tables this repository reads but does not own, in the shape the test
  # suite and the staging bootstrap run on. Every statement in the file is
  # idempotent, so an already prepared database is left as it is. The file ships
  # inside this application's priv directory and holds only DDL written in this
  # repository, so neither the path nor the statements come from input.
  # sobelow_skip ["SQL.Query", "Traversal.FileModule"]
  def create_shared_tables! do
    :techtree
    |> Application.app_dir("priv/repo/shared_tables.sql")
    |> File.read!()
    |> String.split(";\n", trim: true)
    |> Enum.map(&String.trim/1)
    |> Enum.reject(&(&1 == ""))
    |> Enum.each(&Ecto.Adapters.SQL.query!(Techtree.Repo, &1, []))
  end
end
