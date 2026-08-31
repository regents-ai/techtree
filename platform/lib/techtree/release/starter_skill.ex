defmodule Techtree.Release.StarterSkill do
  @moduledoc """
  The introductory Skill, as the exact file a participant's agent fetches.

  This is the one published object that does not come out of the generated
  catalog bundle. The bundle holds the protocol graph `techtree-python`
  produces; the starter Skill is a release artifact — a single `SKILL.md` that
  the installation contract points at so that the CLI can fetch it, hash it, and
  mount it. It ships inside this application, beside the bundle rather than in
  it.

  It is addressed by the digest of the **file**, because the address returns the
  file: the bytes this endpoint hands back hash to `file_digest/0` and to
  nothing else. `tree_digest/0` is a different number — the ordered content
  digest of the one-file Skill *tree* the CLI builds after fetching, and the one
  the CLI checks what it obtained against. Both belong in the installation
  contract, and only the file digest may ever key a URL that serves a file.

  The digests are written here rather than computed from whatever is on disk. A
  constant is what makes drift detectable: if the file and the constant ever
  disagree, `bytes/0` refuses instead of publishing a Skill nobody approved.
  """

  alias Techtree.Catalog.Digest
  alias Techtree.Catalog.Error

  @name "hello-world-starter-v1"
  @relative_path "skills/hello-world-starter-v1/SKILL.md"
  @media_type "text/markdown"

  # The sha256 of the exact bytes of
  # `techtree-python/release/skills/hello-world-starter-v1/SKILL.md`, and their
  # count.
  @file_digest "sha256:2aff27070177d9f37b99d5bef6fa372586887e78180005195cb808971ae55a4c"
  @size 1496

  # The ordered content-tree digest of the one-file Skill built from those
  # bytes: `starter_skill_digest` in the ReleaseCore every repository copies.
  @tree_digest "sha256:596d1368ac157975accce7ceff835eed6bfb789eaf68528a0aefa25a68793b0b"

  @doc """
  The name the installation contract publishes this Skill under.
  """
  @spec name() :: String.t()
  def name, do: @name

  @doc """
  The digest of the exact file bytes, which is also the address it is served at.
  """
  @spec file_digest() :: String.t()
  def file_digest, do: @file_digest

  @doc """
  The digest of the Skill tree those bytes are mounted as, which addresses
  nothing.
  """
  @spec tree_digest() :: String.t()
  def tree_digest, do: @tree_digest

  @doc """
  How many bytes the address returns.
  """
  @spec size() :: pos_integer()
  def size, do: @size

  @doc """
  The media type a `SKILL.md` is served as.
  """
  @spec media_type() :: String.t()
  def media_type, do: @media_type

  @doc """
  Where the file lives inside the release directory.
  """
  @spec relative_path() :: String.t()
  def relative_path, do: @relative_path

  @doc """
  Whether one digest is the address of the starter Skill.
  """
  @spec addressed_by?(String.t()) :: boolean()
  def addressed_by?(digest), do: digest == @file_digest

  @doc """
  The exact file bytes, hashed again before they are returned.

  Refuses with `:catalog_object_digest_mismatch` when the file on disk is no
  longer the file this release pinned, and with `:catalog_object_missing` when
  it is not there at all.
  """
  @spec bytes() :: {:ok, binary(), String.t()} | {:error, Error.t()}
  def bytes do
    path = Path.join(Techtree.Release.starter_skill_root(), @relative_path)

    with {:ok, bytes} <- read(path) do
      case Digest.verify_bytes(bytes, @file_digest) do
        :ok ->
          {:ok, bytes, @media_type}

        {:error, computed} ->
          {:error,
           Error.object_digest_mismatch(
             "the served bytes do not match the digest they are filed under",
             %{
               "path" => @relative_path,
               "expected_digest" => @file_digest,
               "computed_digest" => computed
             }
           )}
      end
    end
  end

  defp read(path) do
    case File.read(path) do
      {:ok, bytes} ->
        {:ok, bytes}

      {:error, reason} ->
        {:error,
         Error.object_missing("this release does not ship the starter Skill", %{
           "path" => @relative_path,
           "reason" => to_string(:file.format_error(reason))
         })}
    end
  end
end
