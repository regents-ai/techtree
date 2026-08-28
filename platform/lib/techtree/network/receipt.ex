defmodule Techtree.Network.Receipt do
  @moduledoc """
  What the network says back when it accepts a published run, and when it marks
  one withdrawn.

  Both are signed envelopes: a payload, the digest of that payload's own
  canonical form, and a detached signature over that digest string. That is the
  shape every signed document in this protocol already uses, and it is here for
  a structural reason rather than a stylistic one. The participant's own tooling
  is required to check that the payload digest matches the payload bytes, and a
  flat document has no payload digest and no structural answer to *which*
  members the signature covers — so two implementations can disagree about the
  covered set and neither is wrong. An envelope answers it by construction: the
  signature is over the digest, the digest is over the canonical bytes of
  `payload`, and `payload` is one object with a boundary.

  The two payloads are fixed by
  `techtree-python/schemas/v1alpha1/publication-receipt.schema.json` and
  `publication-withdrawal-receipt.schema.json`, which the participant's CLI
  validates against strictly. This module builds exactly those members and no
  others.

  Four things about the publication receipt deserve saying out loud.

  *`checks` is the list the ingest actually ran.* It is built from
  `Techtree.Network.Bundle.checks/0` — the same checks the detail page prints
  and the same checks `Techtree.Network.Bundle` walks in order — with their own
  identifiers and their own sentences. It is not a constant written here, and
  it is not a count dressed up as a list. Every one of them is reported as
  passed because a receipt only ever exists for a submission that passed all of
  them: a check that does not hold produces a refusal naming it, and no row and
  no receipt.

  *`accepted_at` is when the log accepted it*, chosen before the row is written
  so that the row and the receipt cannot disagree, and in UTC with a `Z` on the
  end. It is not when the run happened, which is the participant's business and
  is inside their own signed bundle.

  *`entry_url` is the verified detail page*, and it is addressed by the bundle
  digest. It is deliberately not an address that returns the submitted bytes: a
  public address returning the file mapping hands over the whole bundle however
  it is wrapped in JSON, and 0038 defers that.

  *The signature is the countersignature.* A holder of a receipt checks it by
  canonicalizing `payload`, hashing it, comparing that to `payload_digest`, and
  verifying `signature` over that digest string under the key at
  `GET /api/v1/publication-keys/<key id>`. The key id in that address is the
  SHA-256 of the key itself, so a receipt naming a key it does not carry is
  caught for free.

  The withdrawal receipt is the same envelope over a smaller payload: which run,
  when this log marked it withdrawn, where the entry still lives, and the key
  that signed. It names where the entry *still is* rather than saying it is
  gone, because withdrawal is an appended event and the entry stays.

  Both are served as canonical bytes, so the payload a verifier reconstructs is
  a member-for-member subset of what they were handed rather than a
  re-rendering of it. The publication receipt is also stored on the entry, so a
  participant who retries after a lost response is handed the identical
  document rather than a second one that agrees with the first.
  """

  alias Techtree.Canonical
  alias Techtree.Catalog.Digest
  alias Techtree.Network.Bundle
  alias Techtree.Network.Key
  alias Techtree.Network.PublicationEntry

  @receipt_version "techtree.publication-receipt.v1alpha1"
  @withdrawal_receipt_version "techtree.publication-withdrawal-receipt.v1alpha1"

  @doc """
  The signed receipt for one entry on the log.
  """
  @spec issue(PublicationEntry.t(), String.t(), Key.t()) :: %{String.t() => term()}
  def issue(%PublicationEntry{} = entry, origin, %Key{} = key) when is_binary(origin) do
    seal(
      %{
        "schema_version" => @receipt_version,
        "id" => entry.id,
        "run_id" => entry.run_id,
        "log_sequence" => entry.log_sequence,
        "bundle_digest" => entry.bundle_digest,
        "accepted_at" => utc(entry.accepted_at),
        "checks" => checks(),
        "entry_url" => entry_url(entry, origin),
        "public_key" => Key.reference(key)
      },
      key
    )
  end

  @doc """
  The signed record that one entry is marked withdrawn.
  """
  @spec issue_withdrawal(PublicationEntry.t(), String.t(), Key.t()) :: %{String.t() => term()}
  def issue_withdrawal(%PublicationEntry{} = entry, origin, %Key{} = key)
      when is_binary(origin) do
    seal(
      %{
        "schema_version" => @withdrawal_receipt_version,
        "bundle_digest" => entry.bundle_digest,
        "withdrawn_at" => utc(entry.withdrawn_at),
        "entry_url" => entry_url(entry, origin),
        "public_key" => Key.reference(key)
      },
      key
    )
  end

  @doc """
  The canonical bytes of one receipt, which is how it is sent.
  """
  @spec encode(%{String.t() => term()}) :: binary()
  def encode(receipt) when is_map(receipt), do: Canonical.encode!(receipt)

  @doc """
  The digest the signature on one receipt was made over.
  """
  @spec payload_digest(%{String.t() => term()}) :: String.t()
  def payload_digest(%{"payload_digest" => digest}), do: digest

  defp seal(payload, key) do
    digest = Digest.hash_bytes(Canonical.encode!(payload))

    %{
      "payload" => payload,
      "payload_digest" => digest,
      "signature" => Key.countersign(key, digest)
    }
  end

  defp entry_url(entry, origin), do: origin <> "/runs/" <> entry.bundle_digest

  # RFC 3339 in UTC with a `Z` on the end, which is what the schema requires and
  # what a microsecond-precision UTC timestamp already prints as.
  defp utc(at), do: at |> DateTime.shift_zone!("Etc/UTC") |> DateTime.to_iso8601()

  defp checks do
    Enum.map(Bundle.checks(), fn {id, detail} ->
      %{"id" => to_string(id), "passed" => true, "detail" => detail}
    end)
  end
end
