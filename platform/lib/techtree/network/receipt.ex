defmodule Techtree.Network.Receipt do
  @moduledoc """
  What the network says back when it accepts a published run.

  A receipt is a `techtree.publication-receipt.v1alpha1` document, and its shape
  is fixed in decision 0038 rather than here, because the participant's own CLI
  validates it strictly and refuses a publication whose receipt is not that
  document exactly. Ten members, no more and no fewer: which log this is, where
  in it the entry landed, which bundle was accepted, when, which checks ran,
  where the entry can now be read, the network's key, and the network's
  signature.

  Three of those deserve saying out loud.

  *`checks` is the list the ingest actually ran.* It is built from
  `Techtree.Network.Bundle.checks/0` — the same eight the detail page prints and
  the same eight `Techtree.Network.Bundle` walks in order — with their own
  identifiers and their own sentences. It is not a constant written here, and
  it is not a count dressed up as a list. Every one of them is reported as
  passed because a receipt only ever exists for a submission that passed all of
  them: a check that does not hold produces a refusal naming it, and no row and
  no receipt.

  *`accepted_at` is when the log accepted it*, taken from the row's own insert
  timestamp in UTC. It is not when the run happened, which is the participant's
  business and is inside their own signed bundle.

  *The signature is the countersignature.* It is Ed25519 over the SHA-256 of
  the RFC 8785 canonical form of this receipt's own payload, where the payload
  is the receipt with the `signature` member removed — every other member
  included, `public_key` among them, so the key cannot be swapped for another
  without breaking the signature. That is the same shape every signed document
  in this protocol uses: canonicalize the payload, hash it, sign the digest
  string. A holder of a receipt therefore checks it by dropping `signature`,
  canonicalizing what is left, hashing it, and verifying the signature over that
  digest under the key at `GET /api/v1/network-key`, without asking this site
  for anything else.

  The response is served as canonical bytes for the same reason: the payload a
  verifier has to reconstruct is then a member-for-member subset of what they
  were handed, rather than a re-rendering of it.
  """

  alias Techtree.Canonical
  alias Techtree.Catalog.Digest
  alias Techtree.Network.Bundle
  alias Techtree.Network.Key
  alias Techtree.Network.Submission

  @schema_version "techtree.publication-receipt.v1alpha1"

  @doc """
  The signed receipt for one entry on the log.
  """
  @spec issue(Submission.t(), String.t(), Key.t()) :: %{String.t() => term()}
  def issue(%Submission{} = entry, entry_url, %Key{} = key) when is_binary(entry_url) do
    payload = payload(entry, entry_url, key)
    digest = Digest.hash_bytes(Canonical.encode!(payload))

    Map.put(payload, "signature", Key.countersign(key, digest))
  end

  @doc """
  The canonical bytes of one receipt, which is how it is sent.
  """
  @spec encode(%{String.t() => term()}) :: binary()
  def encode(receipt) when is_map(receipt), do: Canonical.encode!(receipt)

  defp payload(entry, entry_url, key) do
    %{
      "schema_version" => @schema_version,
      "id" => entry.id,
      "run_id" => entry.run_id,
      "log_sequence" => entry.sequence,
      "bundle_digest" => entry.bundle_digest,
      "accepted_at" => DateTime.to_iso8601(entry.inserted_at),
      "checks" => checks(),
      "entry_url" => entry_url,
      "public_key" => Key.reference(key)
    }
  end

  defp checks do
    Enum.map(Bundle.checks(), fn {id, detail} ->
      %{"id" => to_string(id), "passed" => true, "detail" => detail}
    end)
  end
end
