defmodule Techtree.Release.StarterSkill do
  @moduledoc """
  The starter Skills, one per Climb, as the exact files a participant's agent
  fetches.

  These are the published objects that do not come out of the generated
  catalog bundle. The bundle holds the protocol graph `regents-cli` produces;
  a starter Skill is a release artifact — a single `SKILL.md` that the
  installation contract points at, under its Climb's reference, so that the CLI
  can fetch it, hash it, and mount it. They ship inside this application,
  beside the bundle rather than in it.

  Each is addressed by the digest of the **file**, because the address returns
  the file: the bytes this endpoint hands back hash to `file_digest` and to
  nothing else. `tree_digest` is a different number — the ordered content
  digest of the one-file Skill *tree* the CLI builds after fetching, and the one
  the CLI checks what it obtained against. Both belong in the installation
  contract, and only the file digest may ever key a URL that serves a file.

  The digests are written here rather than computed from whatever is on disk. A
  constant is what makes drift detectable: if a file and its constant ever
  disagree, `bytes/1` refuses instead of publishing a Skill nobody approved.
  """

  alias Techtree.Catalog.Digest
  alias Techtree.Catalog.Error

  @enforce_keys [:climb_reference, :name, :file_digest, :size, :tree_digest]
  defstruct @enforce_keys

  @type t :: %__MODULE__{
          climb_reference: String.t(),
          name: String.t(),
          file_digest: String.t(),
          size: pos_integer(),
          tree_digest: String.t()
        }

  @media_type "text/markdown"

  # `file_digest` and `size` are the sha256 and the count of the exact bytes of
  # `priv/release/skills/<name>/SKILL.md`. `tree_digest` is the ordered
  # content-tree digest of the one-file Skill built from those bytes: the
  # Climb's `starter_skill_digest` in the ReleaseCore every repository copies.
  @starters [
    %{
      climb_reference: "hello-world-climb@3",
      name: "hello-world-starter-v1",
      file_digest: "sha256:2aff27070177d9f37b99d5bef6fa372586887e78180005195cb808971ae55a4c",
      size: 1496,
      tree_digest: "sha256:596d1368ac157975accce7ceff835eed6bfb789eaf68528a0aefa25a68793b0b"
    },
    %{
      climb_reference: "frontier-cs-open-ended-climb@3",
      name: "frontier-cs-starter-v4",
      file_digest: "sha256:c09dbdd7d5baf7ffa2ab79cf568c14d0f4c83f95cb83dc099ab4bc73b819f669",
      size: 4675,
      tree_digest: "sha256:c93c985b1017d976408239b2583bff7248507032cb32c7aeb20edd685fbc86a6"
    },
    %{
      climb_reference: "tasksmith-climb@2",
      name: "tasksmith-starter-v1",
      file_digest: "sha256:6e36be766e6d2ac16f5d8feda3a09f5b1337a6d9f7d1b306cdd44dbe456377d4",
      size: 1308,
      tree_digest: "sha256:974fafc5bce1d489fe332c7bdc8e9b9ecb38b873d407ac7d38c70f098362b595"
    }
  ]

  @doc """
  Every starter Skill this release ships.
  """
  @spec all() :: [t()]
  def all, do: Enum.map(@starters, &struct!(__MODULE__, &1))

  @doc """
  The starter Skill of one Climb.
  """
  @spec for_climb(String.t()) :: {:ok, t()} | :error
  def for_climb(reference) do
    find(&(&1.climb_reference == reference))
  end

  @doc """
  The starter Skill one digest is the address of.
  """
  @spec addressed_by(String.t()) :: {:ok, t()} | :error
  def addressed_by(digest) do
    find(&(&1.file_digest == digest))
  end

  @doc """
  The media type a `SKILL.md` is served as.
  """
  @spec media_type() :: String.t()
  def media_type, do: @media_type

  @doc """
  Where a starter Skill's file lives inside the release directory.
  """
  @spec relative_path(t()) :: String.t()
  def relative_path(%__MODULE__{name: name}), do: "skills/#{name}/SKILL.md"

  @doc """
  The exact file bytes, hashed again before they are returned.

  Refuses with `:catalog_object_digest_mismatch` when the file on disk is no
  longer the file this release pinned, and with `:catalog_object_missing` when
  it is not there at all.
  """
  @spec bytes(t()) :: {:ok, binary(), String.t()} | {:error, Error.t()}
  def bytes(%__MODULE__{file_digest: file_digest} = starter) do
    relative_path = relative_path(starter)

    with {:ok, bytes} <- read(relative_path) do
      case Digest.verify_bytes(bytes, file_digest) do
        :ok ->
          {:ok, bytes, @media_type}

        {:error, computed} ->
          {:error,
           Error.object_digest_mismatch(
             "the served bytes do not match the digest they are filed under",
             %{
               "path" => relative_path,
               "expected_digest" => file_digest,
               "computed_digest" => computed
             }
           )}
      end
    end
  end

  defp find(match?) do
    case Enum.find(all(), match?) do
      nil -> :error
      starter -> {:ok, starter}
    end
  end

  # The path is one of this module's own fixed files inside the application.
  # sobelow_skip ["Traversal.FileModule"]
  defp read(relative_path) do
    case File.read(Path.join(Techtree.Release.starter_skill_root(), relative_path)) do
      {:ok, bytes} ->
        {:ok, bytes}

      {:error, reason} ->
        {:error,
         Error.object_missing("this release does not ship the starter Skill", %{
           "path" => relative_path,
           "reason" => to_string(:file.format_error(reason))
         })}
    end
  end
end
