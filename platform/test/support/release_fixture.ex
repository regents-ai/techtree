defmodule Techtree.ReleaseFixture do
  @moduledoc """
  The release artifacts this application ships, and ways to damage a copy.

  Unlike the catalog bundle, the starter Skills are not fixtures at all: the
  files under test are the ones the release publishes, in `priv/release`. Tests
  that need one read it in place; tests that need one broken copy the release
  into their own temporary directory and point the application at that instead.
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
  Replace one starter Skill inside a copied release directory.
  """
  @spec write_starter_skill!(Path.t(), StarterSkill.t(), binary()) :: :ok
  def write_starter_skill!(release, starter, bytes) do
    File.write!(Path.join(release, StarterSkill.relative_path(starter)), bytes)
  end

  @doc """
  The exact bytes of one starter Skill this release publishes.
  """
  @spec starter_skill_bytes(StarterSkill.t()) :: binary()
  def starter_skill_bytes(starter) do
    File.read!(Path.join(root(), StarterSkill.relative_path(starter)))
  end
end
