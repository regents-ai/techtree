defmodule Techtree.Catalog.Publication do
  @moduledoc """
  Which staged bootstrap release a channel publishes, and how that moves.

  A bootstrap release is immutable: it is filed under the digest of its exact
  bytes, and two rows with the same digest are the same release. What changes is
  a pointer — the `active` flag the channel's unique index allows exactly one
  row to hold — and moving it is the whole of rollback. Nothing is rewritten,
  nothing is deleted, and nothing a participant already installed is touched:
  the previous release stays staged and can be published again by naming its
  digest.

  Two rules the switch enforces before it moves anything. The digest must name a
  release staged on this channel, so a typo publishes nothing rather than the
  wrong thing. And the stored bytes are hashed again first: a payload that no
  longer matches the digest it is filed under is refused here, exactly as it
  would be refused at request time, because publishing it would make the site
  serve an installation contract nobody approved.

  Writing is the importer's privilege everywhere else in this domain. This is
  the one other place, and for the same reason: it is release machinery run
  deliberately by an operator, never anything a request can reach.
  """

  require Ash.Query

  alias Techtree.Catalog
  alias Techtree.Catalog.BootstrapRelease
  alias Techtree.Catalog.Digest
  alias Techtree.Catalog.Error

  @internal [authorize?: false]

  @typedoc """
  What one switch did: the channel, the digest now published, and the digest
  that was published before it — `nil` when the channel published nothing.
  """
  @type switch :: %{channel: String.t(), published: String.t(), previous: String.t() | nil}

  @doc """
  Publish the bootstrap release filed under `digest`.

  Options:

    * `:channel` — the release channel. Defaults to the configured one.
  """
  @spec publish(String.t(), keyword()) :: {:ok, switch()} | {:error, Error.t()}
  def publish(digest, opts \\ []) do
    channel = channel(opts)

    with {:ok, release} <- fetch(digest, channel),
         :ok <- verify_payload(release) do
      switch(release, channel)
    end
  end

  @doc """
  Every bootstrap release staged on a channel, newest first.

  Options:

    * `:channel` — the release channel. Defaults to the configured one.
  """
  @spec list(keyword()) :: [BootstrapRelease.t()]
  def list(opts \\ []) do
    channel = channel(opts)

    BootstrapRelease
    |> Ash.Query.filter(channel == ^channel)
    |> Ash.Query.sort(published_at: :desc, inserted_at: :desc)
    |> Ash.read!(@internal)
  end

  defp switch(release, channel) do
    Ash.transact([BootstrapRelease], fn ->
      previous = retire_published(channel, release.id)
      Catalog.activate_bootstrap_release!(release, @internal)

      %{channel: channel, published: release.payload_digest, previous: previous}
    end)
  end

  # One active release per channel is a database constraint, so the outgoing
  # release lets go of the pointer before the incoming one takes it.
  defp retire_published(channel, incoming_id) do
    BootstrapRelease
    |> Ash.Query.filter(channel == ^channel and active == true)
    |> Ash.read!(@internal)
    |> Enum.reject(&(&1.id == incoming_id))
    |> Enum.map(fn release ->
      Catalog.deactivate_bootstrap_release!(release, @internal)
      release.payload_digest
    end)
    |> List.first()
  end

  defp fetch(digest, channel) do
    if Digest.valid?(digest) do
      BootstrapRelease
      |> Ash.Query.filter(channel == ^channel and payload_digest == ^digest)
      |> Ash.read_one!(@internal)
      |> case do
        nil -> {:error, not_staged(digest, channel)}
        release -> {:ok, release}
      end
    else
      {:error,
       Error.bundle_invalid("a release is named by sha256: and 64 lowercase hex characters", %{
         "digest" => inspect(digest)
       })}
    end
  end

  defp verify_payload(release) do
    case Digest.verify_bytes(release.raw_payload, release.payload_digest) do
      :ok ->
        :ok

      {:error, computed} ->
        {:error,
         Error.object_digest_mismatch(
           "the stored bootstrap payload does not match the digest it is filed under",
           %{
             "expected_digest" => release.payload_digest,
             "computed_digest" => computed
           }
         )}
    end
  end

  defp channel(opts) do
    case Keyword.get(opts, :channel) do
      nil -> Catalog.channel()
      channel when is_binary(channel) -> channel
    end
  end

  defp not_staged(digest, channel) do
    Error.bootstrap_missing("this channel has no bootstrap release under that digest", %{
      "channel" => channel,
      "digest" => digest
    })
  end
end
