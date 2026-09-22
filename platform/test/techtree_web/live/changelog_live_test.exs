defmodule TechtreeWeb.ChangelogLiveTest do
  @moduledoc """
  The changelog is published twice from one text: the repository root
  `CHANGELOG.md`, which GitHub renders, and `priv/changelog.md`, which this
  site renders. They are the same bytes or the check fails.
  """

  use ExUnit.Case, async: true

  @site Path.expand("../../../priv/changelog.md", __DIR__)
  @root Path.expand("../../../../CHANGELOG.md", __DIR__)

  test "the repository changelog and the site changelog are the same bytes" do
    assert File.read!(@root) == File.read!(@site)
  end
end
