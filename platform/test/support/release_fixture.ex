defmodule Techtree.ReleaseFixture do
  @moduledoc """
  The release artifacts this application ships, and ways to damage a copy.

  Unlike the catalog bundle, the starter Skill is not a fixture at all: the file
  under test is the one the release publishes, in `priv/release`. Tests that
  need it read it in place; tests that need it broken copy it into their own
  temporary directory and point the application at that instead.
  """

  alias Techtree.Release
  alias Techtree.Release.StarterSkill

  @doc """
  The release directory this build serves. Never write to it.
  """
  @spec root() :: Path.t()
  def root, do: Release.starter_skill_root()

  @doc """
  A writable copy of the release directory inside `destination`.
  """
  @spec copy!(Path.t()) :: Path.t()
  def copy!(destination) do
    release = Path.join(destination, "release")
    File.mkdir_p!(release)
    File.cp_r!(root(), release)
    release
  end

  @doc """
  Serve release artifacts from `root` for the duration of the calling test.
  """
  @spec use_release(Path.t()) :: :ok
  def use_release(root) do
    previous = Application.get_env(:techtree, Release, [])

    Application.put_env(
      :techtree,
      Release,
      Keyword.merge(previous, starter_skill_root: root)
    )

    ExUnit.Callbacks.on_exit(fn ->
      Application.put_env(:techtree, Release, previous)
    end)

    :ok
  end

  @doc """
  Replace the starter Skill inside a copied release directory.
  """
  @spec write_starter_skill!(Path.t(), binary()) :: :ok
  def write_starter_skill!(release, bytes) do
    File.write!(Path.join(release, StarterSkill.relative_path()), bytes)
  end

  @doc """
  The exact bytes of the starter Skill this release publishes.
  """
  @spec starter_skill_bytes() :: binary()
  def starter_skill_bytes do
    File.read!(Path.join(root(), StarterSkill.relative_path()))
  end
end
