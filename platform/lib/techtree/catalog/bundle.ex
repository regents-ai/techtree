defmodule Techtree.Catalog.Bundle do
  @moduledoc """
  One generated catalog export, on disk, as this application may read it.

  A bundle is the directory `techtree-python` produced (spec section 8.7): the
  catalog index, the release provenance beside it, the bootstrap release for the
  channel, and the content-addressed objects the index points at. This module is
  the only place that turns a catalog-relative path into a file, and it refuses
  every path that could name something the bundle does not contain — absolute
  paths, `..` segments, and paths that reach outside the root through a symlink.

  Nothing here decides whether the bundle is *believable*; that is
  `Techtree.Catalog.Verifier`. What is decided here is what the bundle *is*: the
  exact index and bootstrap bytes, the parsed documents beside them, and the flat
  list of entries the index declares.
  """

  alias Techtree.Catalog.Digest
  alias Techtree.Catalog.Error

  @source_filename "source.json"
  @catalog_filename "catalog.json"
  @bootstrap_filename "bootstrap.json"

  # Every object a v1alpha1 catalog ships is a JSON document. The index states
  # the media type for content-addressed objects; Climb manifests are named by
  # reference rather than by digest, so their media type is fixed here.
  @json_media_type "application/json"

  # What the index calls each kind of object, and what this application calls
  # it. A kind outside this map becomes `:unknown`, which the verifier rejects.
  @kinds %{
    "campaign" => :campaign,
    "data_policy" => :data_policy,
    "taskset_validation" => :taskset_validation,
    "validation_evidence" => :validation_evidence
  }

  @type kind ::
          :climb
          | :campaign
          | :data_policy
          | :taskset_validation
          | :validation_evidence
          | :unknown

  @type entry :: %{
          kind: kind(),
          reference: String.t() | nil,
          digest: String.t(),
          relative_path: String.t(),
          media_type: String.t()
        }

  @type t :: %__MODULE__{
          root: Path.t(),
          source: map(),
          catalog_bytes: binary(),
          catalog: map(),
          bootstrap_bytes: binary(),
          bootstrap: map()
        }

  defstruct [:root, :source, :catalog_bytes, :catalog, :bootstrap_bytes, :bootstrap]

  @doc """
  The three named documents of the bundle at `root`, with their exact bytes.

  Raises `Techtree.Catalog.Error` when a named document is missing or is not a
  JSON object. The objects the index points at are not read here — reading them
  is verification, and it is paid for once, by the verifier.
  """
  @spec load!(Path.t()) :: t()
  def load!(root) do
    root = Path.expand(root)

    if not File.dir?(root) do
      raise Error.bundle_invalid("the catalog bundle directory does not exist")
    end

    {_source_bytes, source} = read_document!(root, @source_filename)
    {catalog_bytes, catalog} = read_document!(root, @catalog_filename)
    {bootstrap_bytes, bootstrap} = read_document!(root, @bootstrap_filename)

    %__MODULE__{
      root: root,
      source: source,
      catalog_bytes: catalog_bytes,
      catalog: catalog,
      bootstrap_bytes: bootstrap_bytes,
      bootstrap: bootstrap
    }
  end

  @doc """
  The file one catalog-relative path names, or why it may not be read.

  A path is resolvable only when it is relative and normalized, stays under the
  bundle root, and names a regular file — including at every intermediate
  segment, so that a symlinked directory cannot smuggle the resolution out of
  the bundle.
  """
  @spec object_path(t(), String.t()) :: {:ok, Path.t()} | {:error, Error.t()}
  def object_path(%__MODULE__{root: root}, relative_path), do: resolve(root, relative_path)

  @doc """
  The same resolution, against a bundle root that has not been loaded.

  The exact-byte read path resolves paths from the imported index against the
  configured catalog root, and must apply the identical rules.
  """
  @spec resolve(Path.t(), String.t()) :: {:ok, Path.t()} | {:error, Error.t()}
  def resolve(root, relative_path) when is_binary(relative_path) do
    with :ok <- check_relative(relative_path),
         :ok <- check_no_links(root, relative_path) do
      {:ok, Path.join(root, relative_path)}
    end
  end

  def resolve(_root, relative_path) do
    {:error,
     Error.bundle_invalid("a catalog path must be a string", %{
       "path" => inspect(relative_path)
     })}
  end

  @doc """
  The exact bytes of the object filed under `digest`, digest-verified.
  """
  @spec read_object!(t(), String.t()) :: binary()
  def read_object!(%__MODULE__{} = bundle, digest) do
    case fetch_entry(bundle, digest) do
      {:ok, entry} ->
        read_entry!(bundle, entry)

      :error ->
        raise Error.object_missing("the catalog index has no object filed under this digest", %{
                "digest" => digest
              })
    end
  end

  @doc """
  The exact bytes one index entry names, digest-verified.
  """
  @spec read_entry!(t(), entry()) :: binary()
  def read_entry!(%__MODULE__{} = bundle, entry) do
    path =
      case object_path(bundle, entry.relative_path) do
        {:ok, path} -> path
        {:error, error} -> raise error
      end

    bytes =
      case File.read(path) do
        {:ok, bytes} ->
          bytes

        {:error, reason} ->
          raise Error.object_missing("a catalog object could not be read", %{
                  "path" => entry.relative_path,
                  "reason" => to_string(:file.format_error(reason))
                })
      end

    case Digest.verify_bytes(bytes, entry.digest) do
      :ok ->
        bytes

      {:error, computed} ->
        raise Error.object_digest_mismatch(
                "a catalog object does not match the digest it is filed under",
                %{
                  "path" => entry.relative_path,
                  "expected_digest" => entry.digest,
                  "computed_digest" => computed
                }
              )
    end
  end

  @doc """
  Every object the index declares: the public Climbs, then the content-addressed
  objects in digest order, so that two imports of one bundle stage the same rows
  in the same order.
  """
  @spec list_entries(t()) :: [entry()]
  def list_entries(%__MODULE__{catalog: catalog}) do
    climbs =
      catalog
      |> Map.get("climbs", [])
      |> Enum.map(fn climb ->
        %{
          kind: :climb,
          reference: climb["reference"],
          digest: climb["digest"],
          relative_path: climb["path"],
          media_type: @json_media_type
        }
      end)

    objects =
      catalog
      |> Map.get("objects", %{})
      |> Enum.sort_by(fn {digest, _location} -> digest end)
      |> Enum.map(fn {digest, location} ->
        %{
          kind: Map.get(@kinds, location["kind"], :unknown),
          reference: nil,
          digest: digest,
          relative_path: location["path"],
          media_type: location["media_type"]
        }
      end)

    climbs ++ objects
  end

  @doc """
  The index entry filed under one digest.
  """
  @spec fetch_entry(t(), String.t()) :: {:ok, entry()} | :error
  def fetch_entry(%__MODULE__{} = bundle, digest) do
    bundle
    |> list_entries()
    |> Enum.find(&(&1.digest == digest))
    |> case do
      nil -> :error
      entry -> {:ok, entry}
    end
  end

  @doc """
  The `techtree-python` revision this bundle was generated from.
  """
  @spec source_revision(t()) :: String.t() | nil
  def source_revision(%__MODULE__{source: source}), do: source["techtree_python_revision"]

  @doc """
  The digest of the exact catalog index bytes.
  """
  @spec catalog_digest(t()) :: String.t()
  def catalog_digest(%__MODULE__{catalog_bytes: bytes}), do: Digest.hash_bytes(bytes)

  @doc """
  The digest of the exact bootstrap release bytes.
  """
  @spec bootstrap_digest(t()) :: String.t()
  def bootstrap_digest(%__MODULE__{bootstrap_bytes: bytes}), do: Digest.hash_bytes(bytes)

  @doc """
  The kinds of content-addressed object a v1alpha1 catalog may file.
  """
  @spec kinds() :: %{String.t() => kind()}
  def kinds, do: @kinds

  @doc """
  The media type every object in a v1alpha1 catalog is served as.
  """
  @spec json_media_type() :: String.t()
  def json_media_type, do: @json_media_type

  @doc """
  The name of the generated catalog index inside a bundle.
  """
  @spec catalog_filename() :: String.t()
  def catalog_filename, do: @catalog_filename

  @doc """
  The names of the three documents every bundle carries.
  """
  @spec filenames() :: [String.t()]
  def filenames, do: [@source_filename, @catalog_filename, @bootstrap_filename]

  defp read_document!(root, filename) do
    path = Path.join(root, filename)

    bytes =
      case File.read(path) do
        {:ok, bytes} ->
          bytes

        {:error, reason} ->
          raise Error.bundle_invalid("the catalog bundle is missing a required document", %{
                  "path" => filename,
                  "reason" => to_string(:file.format_error(reason))
                })
      end

    case Jason.decode(bytes) do
      {:ok, document} when is_map(document) ->
        {bytes, document}

      _other ->
        raise Error.bundle_invalid("a catalog bundle document is not a JSON object", %{
                "path" => filename
              })
    end
  end

  defp check_relative(path) do
    segments = String.split(path, "/")

    cond do
      String.contains?(path, "\\") ->
        {:error, path_error("a catalog path uses forward slashes", path)}

      String.starts_with?(path, "/") ->
        {:error, path_error("a catalog path is relative to the bundle root", path)}

      Enum.any?(segments, &(&1 in ["", ".", ".."])) ->
        {:error, path_error("a catalog path is a normalized relative path", path)}

      true ->
        :ok
    end
  end

  defp check_no_links(root, path) do
    path
    |> String.split("/")
    |> Enum.reduce_while({:ok, root}, fn segment, {:ok, parent} ->
      candidate = Path.join(parent, segment)

      case File.lstat(candidate) do
        {:ok, %File.Stat{type: :directory}} -> {:cont, {:ok, candidate}}
        {:ok, %File.Stat{type: :regular}} -> {:cont, {:ok, candidate}}
        {:ok, %File.Stat{}} -> {:halt, {:error, path_error("a catalog path is a link", path)}}
        {:error, _reason} -> {:halt, {:error, missing_error(path)}}
      end
    end)
    |> case do
      {:ok, _path} -> :ok
      {:error, error} -> {:error, error}
    end
  end

  defp path_error(message, path) do
    Error.bundle_invalid(message, %{"path" => path})
  end

  defp missing_error(path) do
    Error.object_missing("the catalog index names a file the bundle does not ship", %{
      "path" => path
    })
  end
end
