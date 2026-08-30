defmodule Techtree.Catalog.ConcreteCoordinates do
  @moduledoc """
  What a bootstrap release that says it is not a placeholder has to be.

  `placeholder_release` is a stated fact, not an inference (decision 0007 R10).
  Saying `true` labels every coordinate below as a development stand-in and
  keeps the public install flow shut. Saying `false` is a promise that each of
  them is concrete and immutable: an exact version, a full commit, an address a
  machine can fetch from, and a hash for anything it fetches. A release that
  makes that promise while still carrying `0.0.0-placeholder`, an empty string,
  `latest`, `main`, a shortened commit, a `placeholder.invalid` address, an
  image tag that can be repointed, or an artifact with no hash beside it is the
  one failure mode with no safe outcome — it sends a stranger to install
  something nobody chose. So it is refused at import.

  The checks are two kinds. A handful are named coordinates whose shape is
  fixed: the CLI version, the two revisions, the plugin repository, and the
  starter Skill's address, which is keyed by the digest of the file it returns
  and never by the digest of the tree that file is mounted as. The rest is
  a sweep of every string in the document, because a placeholder is a placeholder
  wherever a future schema puts it, and a rule that only looks where today's
  fields are would quietly stop covering tomorrow's.

  One field is exempt from one rule, deliberately: a channel is a name rather
  than a reference, and `stable` is a perfectly good channel and a terrible
  commit.
  """

  alias Techtree.Catalog.Digest
  alias Techtree.Catalog.Error

  @commit_length 40

  # Values that name something nobody has chosen yet.
  @placeholder ~r/placeholder|unchosen|changeme|\bTBD\b|\bTODO\b|\bFIXME\b/i

  # RFC 6761 reserves `.invalid`: an address under it is guaranteed to resolve
  # to nothing, which is what makes it a good placeholder and an impossible
  # release coordinate.
  @reserved_host ~r/\.invalid(\/|:|$)/i

  # References that can be repointed at other bytes after they are published.
  @mutable ~w(latest main master head trunk edge nightly dev develop unstable tip)

  # A run of zeros long enough to be a filled-in blank rather than a number.
  @zeroed ~r/\A(sha256:)?0{8,}\z/

  # A version a release can be reinstalled from: it starts at a number, and it
  # is not all zeros.
  @version ~r/\A\d+\.\d+/
  @zero_version ~r/\A0+\.0+(\.0+)?([^\d]|$)/

  # A container image is immutable only when it is named by digest.
  @image_digest ~r/@sha256:[0-9a-f]{64}\z/

  # A channel is a name, not a reference. Everything else in the document is a
  # coordinate, and a coordinate that spells a moving target is refused.
  @named_not_referenced ["channel"]

  @doc """
  Whether every coordinate in this bootstrap release is concrete.
  """
  @spec verify(map()) :: :ok | {:error, Error.t()}
  def verify(bootstrap) when is_map(bootstrap) do
    with :ok <- check_version(bootstrap, ["cli", "version"]),
         :ok <- check_version(bootstrap, ["minimums", "hermes_version"]),
         :ok <- check_commit(bootstrap, ["cli", "source_revision"]),
         :ok <- check_commit(bootstrap, ["hermes_plugin", "revision"]),
         :ok <- check_repository(bootstrap, ["hermes_plugin", "repository"]),
         :ok <- sweep(bootstrap, []) do
      check_starter_skill_address(bootstrap)
    end
  end

  # -- Named coordinates ----------------------------------------------------

  defp check_version(bootstrap, path) do
    value = get_in(bootstrap, path)

    if is_binary(value) and value =~ @version and not (value =~ @zero_version) do
      :ok
    else
      {:error, refuse("is not an exact version", path, value)}
    end
  end

  defp check_commit(bootstrap, path) do
    value = get_in(bootstrap, path)

    if is_binary(value) and byte_size(value) == @commit_length and
         value =~ ~r/\A[0-9a-f]+\z/ do
      :ok
    else
      {:error, refuse("is not a full lowercase commit", path, value)}
    end
  end

  defp check_repository(bootstrap, path) do
    value = get_in(bootstrap, path)

    if is_binary(value) and value =~ ~r|\A[\w.-]+/[\w.-]+\z| do
      :ok
    else
      {:error, refuse("is not an owner/name repository", path, value)}
    end
  end

  # The starter Skill is served as a file, so its address is keyed by the digest
  # of that file and by nothing else (decision 0023). Keying it by the digest of
  # the Skill *tree* would publish an address whose bytes never hash to the
  # number naming them, and a fetcher checking the wrong half would either
  # refuse a good Skill or accept whatever answered.
  #
  # Checked after the sweep, so that a spoiled digest is reported as the spoiled
  # digest rather than as the address that stopped matching it.
  defp check_starter_skill_address(bootstrap) do
    path = ["starter_skill", "object_url"]
    address = get_in(bootstrap, path)
    file_digest = get_in(bootstrap, ["starter_skill", "file_digest"])

    if is_binary(address) and is_binary(file_digest) and
         String.ends_with?(address, "/" <> file_digest) do
      :ok
    else
      {:error, refuse("is not keyed by the digest of the file it returns", path, address)}
    end
  end

  # -- The sweep ------------------------------------------------------------

  defp sweep(document, path) when is_map(document) do
    with :ok <- check_hash_beside_address(document, path) do
      reduce_while_ok(document, fn {key, value} -> sweep(value, path ++ [key]) end)
    end
  end

  defp sweep(list, path) when is_list(list) do
    list
    |> Enum.with_index()
    |> reduce_while_ok(fn {value, index} -> sweep(value, path ++ [to_string(index)]) end)
  end

  defp sweep(value, path) when is_binary(value) do
    key = List.last(path)

    cond do
      value == "" ->
        {:error, refuse("is empty", path, value)}

      value =~ @placeholder ->
        {:error, refuse("names a placeholder", path, value)}

      value =~ @reserved_host ->
        {:error, refuse("names a reserved .invalid host", path, value)}

      value =~ @zeroed ->
        {:error, refuse("is a filled-in blank", path, value)}

      mutable?(value, path) ->
        {:error, refuse("is a mutable reference", path, value)}

      hash_key?(key) and not Digest.valid?(value) ->
        {:error, refuse("is not a hash", path, value)}

      image_key?(key) and not (value =~ @image_digest) ->
        {:error, mutable_image(path, value)}

      true ->
        :ok
    end
  end

  defp sweep(_value, _path), do: :ok

  # Anything this release tells a machine to fetch is named by an address and a
  # hash together. An address on its own is an instruction to trust whatever
  # answers it.
  defp check_hash_beside_address(document, path) do
    case Enum.find(Map.keys(document), &address_key?/1) do
      nil ->
        :ok

      address ->
        if Enum.any?(Map.keys(document), &hash_key?/1) do
          :ok
        else
          {:error, refuse("has no hash beside it", path ++ [address], document[address])}
        end
    end
  end

  defp mutable?(_value, @named_not_referenced), do: false

  defp mutable?(value, _path) do
    downcased = String.downcase(value)

    Enum.any?(@mutable, fn reference ->
      downcased == reference or
        String.ends_with?(downcased, [":" <> reference, "@" <> reference, "#" <> reference])
    end)
  end

  defp address_key?(key), do: key in ["object_url", "url", "download_url"]

  defp hash_key?(key) do
    is_binary(key) and
      (String.ends_with?(key, "digest") or String.ends_with?(key, "hash") or
         String.ends_with?(key, "sha256"))
  end

  defp image_key?(key), do: key in ["image", "image_ref"]

  # -- Refusals -------------------------------------------------------------

  defp refuse(problem, path, value) do
    field = Enum.join(path, ".")

    Error.bundle_invalid(
      "this release states it is not a placeholder, but #{field} #{problem}",
      %{"field" => field, "found" => inspect(value)}
    )
  end

  defp mutable_image(path, value) do
    field = Enum.join(path, ".")

    Error.bundle_invalid(
      "this release states it is not a placeholder, but #{field} names an image by tag " <>
        "rather than by digest",
      %{"field" => field, "found" => inspect(value)}
    )
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
