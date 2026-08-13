defmodule Techtree.Catalog.Verifier do
  @moduledoc """
  Whether a generated bundle may be imported.

  The checks here are deliberately narrow (spec section 8.9): raw byte digests,
  safe relative paths, known media types, presence, the shape of the index and
  the bootstrap release, and the absence of a catalog reference that resolves to
  nothing. The `techtree-python` release pipeline stays authoritative for the
  protocol-semantic graph — this application republishes bytes it did not
  produce, and re-deciding their scientific meaning in Elixir would create a
  second answer to a question that already has one.

  What that leaves is exactly the set of failures the website could otherwise
  serve as truth: an object that drifted from its digest, a path that leaves the
  bundle, a Climb that points at a Campaign nobody shipped.
  """

  alias Techtree.Catalog.Bundle
  alias Techtree.Catalog.Digest
  alias Techtree.Catalog.Error

  @catalog_schema_version "techtree.catalog.v1alpha1"
  @bootstrap_schema_version "techtree.bootstrap.v1alpha1"
  @commit_length 40

  @doc """
  Every check, in the order a failure is most cheaply explained.
  """
  @spec verify_bundle(Bundle.t()) :: :ok | {:error, Error.t()}
  def verify_bundle(%Bundle{} = bundle) do
    with :ok <- verify_catalog_index(bundle),
         :ok <- verify_object_locations(bundle),
         :ok <- verify_bootstrap(bundle) do
      verify_no_dangling_refs(bundle)
    end
  end

  @doc """
  Every check, raising the first failure.
  """
  @spec verify_bundle!(Bundle.t()) :: :ok
  def verify_bundle!(%Bundle{} = bundle) do
    case verify_bundle(bundle) do
      :ok -> :ok
      {:error, error} -> raise error
    end
  end

  @doc """
  The index is a v1alpha1 catalog, it addresses each object once, and the
  provenance beside it describes the index that is actually present.
  """
  @spec verify_catalog_index(Bundle.t()) :: :ok | {:error, Error.t()}
  def verify_catalog_index(%Bundle{catalog: catalog} = bundle) do
    with :ok <- check_schema_version(catalog, @catalog_schema_version, "catalog.json"),
         :ok <- check_climb_entries(catalog),
         :ok <- check_object_locations(catalog),
         :ok <- check_unique_paths(bundle) do
      check_source_provenance(bundle)
    end
  end

  @doc """
  Every declared object is present, safely addressable, and hashes to the digest
  the index files it under.
  """
  @spec verify_object_locations(Bundle.t()) :: :ok | {:error, Error.t()}
  def verify_object_locations(%Bundle{} = bundle) do
    bundle
    |> Bundle.list_entries()
    |> reduce_while_ok(fn entry ->
      with {:ok, path} <- Bundle.object_path(bundle, entry.relative_path),
           {:ok, bytes} <- read_file(path, entry.relative_path) do
        case Digest.verify_bytes(bytes, entry.digest) do
          :ok ->
            :ok

          {:error, computed} ->
            {:error,
             Error.object_digest_mismatch(
               "a catalog object does not match the digest it is filed under",
               %{
                 "path" => entry.relative_path,
                 "expected_digest" => entry.digest,
                 "computed_digest" => computed
               }
             )}
        end
      end
    end)
  end

  @doc """
  The bootstrap release names an exact CLI version, an immutable plugin commit,
  argument arrays rather than shell strings, and a Climb this catalog ships.
  """
  @spec verify_bootstrap(Bundle.t()) :: :ok | {:error, Error.t()}
  def verify_bootstrap(%Bundle{bootstrap: bootstrap} = bundle) do
    with :ok <- check_schema_version(bootstrap, @bootstrap_schema_version, "bootstrap.json"),
         :ok <- check_string(bootstrap, ["channel"]),
         :ok <- check_boolean(bootstrap, ["placeholder_release"]),
         :ok <- check_timestamp(bootstrap, ["published_at"]),
         :ok <- check_string(bootstrap, ["minimums", "hermes_version"]),
         :ok <- check_string(bootstrap, ["cli", "distribution"]),
         :ok <- check_string(bootstrap, ["cli", "version"]),
         :ok <- check_argv(bootstrap, ["cli", "install_argv"]),
         :ok <- check_string(bootstrap, ["hermes_plugin", "plugin_id"]),
         :ok <- check_commit(bootstrap, ["hermes_plugin", "revision"]),
         :ok <- check_argv(bootstrap, ["hermes_plugin", "install_argv"]),
         :ok <- check_argv(bootstrap, ["hermes_plugin", "doctor_argv"]),
         :ok <- check_string(bootstrap, ["introductory_climb", "host_prompt"]),
         :ok <- check_string(bootstrap, ["introductory_climb", "reference"]) do
      check_introductory_climb(bundle)
    end
  end

  @doc """
  Every digest one shipped object references is an object this bundle ships.

  The Climb graph is walked the way a reader walks it: Climb to Campaign,
  Campaign to DataPolicy and publisher validation, validation to its normalized
  evidence. A public catalog with a dangling reference is a page that cannot be
  rendered, so it is refused at import rather than at request time.
  """
  @spec verify_no_dangling_refs(Bundle.t()) :: :ok | {:error, Error.t()}
  def verify_no_dangling_refs(%Bundle{} = bundle) do
    bundle
    |> Bundle.list_entries()
    |> Enum.filter(&(&1.kind == :climb))
    |> reduce_while_ok(&verify_climb_graph(bundle, &1))
  end

  defp verify_climb_graph(bundle, entry) do
    with {:ok, climb} <- decode_object(bundle, entry.digest, entry.relative_path),
         {:ok, campaign_digest} <- fetch_digest(climb, ["campaign_spec_digest"], entry),
         :ok <- check_kind(bundle, campaign_digest, :campaign),
         {:ok, campaign} <- decode_object(bundle, campaign_digest, "campaign"),
         {:ok, policy_digest} <- fetch_digest(campaign, ["data_policy_digest"], entry),
         :ok <- check_kind(bundle, policy_digest, :data_policy),
         {:ok, validation_digest} <-
           fetch_digest(campaign, ["taskset", "validation_receipt_digest"], entry),
         :ok <- check_kind(bundle, validation_digest, :taskset_validation),
         {:ok, validation} <- decode_object(bundle, validation_digest, "taskset_validation") do
      verify_validation_evidence(bundle, validation, entry)
    end
  end

  # A publisher validation may carry no normalized evidence. What it may not do
  # is carry a reference to evidence this catalog does not ship.
  defp verify_validation_evidence(bundle, validation, entry) do
    case Map.get(validation, "normalized_evidence") do
      nil ->
        :ok

      evidence when is_map(evidence) ->
        with {:ok, digest} <- fetch_digest(evidence, ["digest"], entry) do
          check_kind(bundle, digest, :validation_evidence)
        end

      _other ->
        {:error,
         Error.bundle_invalid("a publisher validation names malformed evidence", %{
           "path" => entry.relative_path
         })}
    end
  end

  # -- Index checks ---------------------------------------------------------

  defp check_climb_entries(catalog) do
    case Map.get(catalog, "climbs") do
      climbs when is_list(climbs) and climbs != [] ->
        reduce_while_ok(climbs, &check_climb_entry/1)

      _other ->
        {:error, index_error("the catalog index ships no Climb")}
    end
  end

  defp check_climb_entry(climb) when is_map(climb) do
    with :ok <- check_string(climb, ["reference"]),
         :ok <- check_string(climb, ["path"]) do
      check_digest_value(climb["digest"], "a Climb entry")
    end
  end

  defp check_climb_entry(_climb), do: {:error, index_error("a Climb entry is not an object")}

  defp check_object_locations(catalog) do
    case Map.get(catalog, "objects") do
      objects when is_map(objects) ->
        reduce_while_ok(objects, fn {digest, location} ->
          check_object_location(digest, location)
        end)

      _other ->
        {:error, index_error("the catalog index has no object map")}
    end
  end

  defp check_object_location(digest, location) when is_map(location) do
    with :ok <- check_digest_value(digest, "an object entry"),
         :ok <- check_string(location, ["path"]) do
      cond do
        not Map.has_key?(Bundle.kinds(), location["kind"]) ->
          {:error,
           index_error("the catalog index files an object under an unknown kind", %{
             "digest" => digest,
             "kind" => inspect(location["kind"])
           })}

        location["media_type"] != Bundle.json_media_type() ->
          {:error,
           index_error("the catalog index declares a media type this build cannot serve", %{
             "digest" => digest,
             "media_type" => inspect(location["media_type"])
           })}

        true ->
          :ok
      end
    end
  end

  defp check_object_location(digest, _location) do
    {:error, index_error("an object entry is not an object", %{"digest" => digest})}
  end

  defp check_unique_paths(bundle) do
    paths = Enum.map(Bundle.list_entries(bundle), & &1.relative_path)

    case paths -- Enum.uniq(paths) do
      [] ->
        :ok

      [path | _rest] ->
        {:error,
         index_error("two catalog entries claim the same file", %{"path" => to_string(path)})}
    end
  end

  defp check_source_provenance(%Bundle{source: source} = bundle) do
    with :ok <- check_string(source, ["techtree_python_revision"]),
         :ok <- check_string(source, ["generator_version"]),
         :ok <- check_timestamp(source, ["generated_at"]),
         :ok <- check_digest_value(source["catalog_digest"], "the release provenance") do
      declared = source["catalog_digest"]
      actual = Bundle.catalog_digest(bundle)

      if declared == actual do
        :ok
      else
        {:error,
         Error.object_digest_mismatch(
           "the release provenance describes a different catalog index",
           %{"expected_digest" => declared, "computed_digest" => actual}
         )}
      end
    end
  end

  # -- Bootstrap checks -----------------------------------------------------

  defp check_introductory_climb(%Bundle{bootstrap: bootstrap} = bundle) do
    reference = get_in(bootstrap, ["introductory_climb", "reference"])

    references =
      bundle
      |> Bundle.list_entries()
      |> Enum.filter(&(&1.kind == :climb))
      |> Enum.map(& &1.reference)

    if reference in references do
      :ok
    else
      {:error,
       Error.object_missing("the bootstrap release names a Climb this catalog does not ship", %{
         "reference" => reference
       })}
    end
  end

  # -- Shared checks --------------------------------------------------------

  defp check_schema_version(document, expected, filename) do
    case Map.get(document, "schema_version") do
      ^expected ->
        :ok

      other ->
        {:error,
         Error.bundle_invalid("a catalog bundle document has an unsupported schema version", %{
           "path" => filename,
           "expected" => expected,
           "found" => inspect(other)
         })}
    end
  end

  defp check_string(document, path) do
    case get_in(document, path) do
      value when is_binary(value) and value != "" ->
        :ok

      other ->
        {:error,
         Error.bundle_invalid("a required catalog field is not a non-empty string", %{
           "field" => Enum.join(path, "."),
           "found" => inspect(other)
         })}
    end
  end

  # Whether the coordinates below are real is stated, never inferred. A release
  # that forgot to say would otherwise be read as real, which is the one
  # direction of that mistake that could send someone to install nothing.
  defp check_boolean(document, path) do
    case get_in(document, path) do
      value when is_boolean(value) ->
        :ok

      other ->
        {:error,
         Error.bundle_invalid("a required catalog field is not stated as true or false", %{
           "field" => Enum.join(path, "."),
           "found" => inspect(other)
         })}
    end
  end

  defp check_argv(document, path) do
    case get_in(document, path) do
      argv when is_list(argv) and argv != [] ->
        if Enum.all?(argv, &(is_binary(&1) and &1 != "")) do
          :ok
        else
          {:error,
           Error.bundle_invalid("an install instruction is not an array of arguments", %{
             "field" => Enum.join(path, ".")
           })}
        end

      _other ->
        {:error,
         Error.bundle_invalid("an install instruction is not an array of arguments", %{
           "field" => Enum.join(path, ".")
         })}
    end
  end

  defp check_commit(document, path) do
    value = get_in(document, path)

    if is_binary(value) and byte_size(value) == @commit_length and
         String.match?(value, ~r/\A[0-9a-f]+\z/) do
      :ok
    else
      {:error,
       Error.bundle_invalid("a pinned revision is not a full lowercase commit", %{
         "field" => Enum.join(path, ".")
       })}
    end
  end

  defp check_timestamp(document, path) do
    with value when is_binary(value) <- get_in(document, path),
         {:ok, _datetime, _offset} <- DateTime.from_iso8601(value) do
      :ok
    else
      _other ->
        {:error,
         Error.bundle_invalid("a required catalog timestamp is not an ISO 8601 instant", %{
           "field" => Enum.join(path, ".")
         })}
    end
  end

  defp check_digest_value(value, subject) do
    if Digest.valid?(value) do
      :ok
    else
      {:error,
       index_error("#{subject} is not addressed by a sha256 digest", %{
         "digest" => inspect(value)
       })}
    end
  end

  defp check_kind(bundle, digest, expected) do
    case Bundle.fetch_entry(bundle, digest) do
      {:ok, %{kind: ^expected}} ->
        :ok

      {:ok, %{kind: found}} ->
        {:error,
         Error.bundle_invalid("a catalog object is filed under the wrong kind", %{
           "digest" => digest,
           "expected_kind" => to_string(expected),
           "found_kind" => to_string(found)
         })}

      :error ->
        {:error,
         Error.object_missing(
           "a shipped object references a digest this catalog does not ship",
           %{
             "digest" => digest,
             "expected_kind" => to_string(expected)
           }
         )}
    end
  end

  defp fetch_digest(document, path, entry) do
    value = get_in(document, path)

    if Digest.valid?(value) do
      {:ok, value}
    else
      {:error,
       Error.bundle_invalid("a shipped object does not name the digest it depends on", %{
         "path" => entry.relative_path,
         "field" => Enum.join(path, ".")
       })}
    end
  end

  defp decode_object(bundle, digest, subject) do
    with {:ok, entry} <- fetch_entry(bundle, digest, subject),
         {:ok, path} <- Bundle.object_path(bundle, entry.relative_path),
         {:ok, bytes} <- read_file(path, entry.relative_path) do
      case Jason.decode(bytes) do
        {:ok, document} when is_map(document) ->
          {:ok, document}

        _other ->
          {:error,
           Error.bundle_invalid("a catalog object is not a JSON object", %{
             "path" => entry.relative_path
           })}
      end
    end
  end

  defp fetch_entry(bundle, digest, subject) do
    case Bundle.fetch_entry(bundle, digest) do
      {:ok, entry} ->
        {:ok, entry}

      :error ->
        {:error,
         Error.object_missing("the catalog index has no object filed under this digest", %{
           "digest" => digest,
           "referenced_by" => subject
         })}
    end
  end

  defp read_file(path, relative_path) do
    case File.read(path) do
      {:ok, bytes} ->
        {:ok, bytes}

      {:error, reason} ->
        {:error,
         Error.object_missing("a catalog object could not be read", %{
           "path" => relative_path,
           "reason" => to_string(:file.format_error(reason))
         })}
    end
  end

  defp index_error(message, details \\ %{}) do
    Error.bundle_invalid(message, details)
  end

  defp reduce_while_ok(enumerable, check) do
    Enum.reduce_while(enumerable, :ok, fn element, :ok ->
      case check.(element) do
        :ok -> {:cont, :ok}
        {:error, error} -> {:halt, {:error, error}}
      end
    end)
  end
end
