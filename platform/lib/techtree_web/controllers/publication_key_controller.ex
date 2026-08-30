defmodule TechtreeWeb.PublicationKeyController do
  @moduledoc """
  The public half of the key this site countersigns publications with, served
  at the fingerprint of that key.

  A publication receipt carries a signature and the fingerprint of the key that
  made it. That is only checkable if the key itself is somewhere fixed, so it
  is here: `GET /api/v1/publication-keys/<key id>`. The key id is the SHA-256
  of the public key itself, as every other key id in this protocol is, so the
  address is derived from the receipt rather than looked up, and a receipt
  naming a key it does not carry is caught for free — the fingerprint in the
  address, the fingerprint in the receipt and the hash of the served key are
  the same string or the receipt is wrong.

  Somebody holding a receipt — including somebody who trusts neither the
  participant nor this site — fetches this, checks that the fingerprint is the
  hash of the key, and verifies the signature over the receipt's own canonical
  digest. `Techtree.Network.Receipt` documents that procedure from the other
  end.

  What is served is exactly the three-member public key document this protocol
  writes every key as, in canonical form and nothing more, because the
  participant's own tooling validates it as that document and refuses one
  carrying anything else.

  A fingerprint this build is not holding a key for is a `404`: there is
  nothing at that address, and rotation is a new key, a new fingerprint and a
  new address rather than a change of what this one answers. A build with no
  key configured at all answers `503` rather than serving a placeholder or an
  empty document; `Techtree.Network.Key` says why a key is never invented to
  fill the gap.
  """

  use TechtreeWeb, :controller

  alias Techtree.Canonical
  alias Techtree.Catalog.Digest
  alias Techtree.Network.Key
  alias TechtreeWeb.ExactResponse

  @doc """
  Return the network's public signing key, if this is its fingerprint.
  """
  def show(conn, %{"key_id" => key_id}) do
    case Key.load() do
      {:ok, %Key{key_id: ^key_id} = key} ->
        bytes = Canonical.encode!(Key.reference(key))

        ExactResponse.send_exact(
          conn,
          bytes,
          "application/json",
          Digest.hash_bytes(bytes),
          :immutable
        )

      {:ok, %Key{}} ->
        ExactResponse.send_error(
          conn,
          404,
          :network_key_missing,
          "this site countersigns with no key under that fingerprint",
          false
        )

      :error ->
        ExactResponse.send_error(
          conn,
          503,
          :network_key_unavailable,
          "this site holds no signing key, so it is countersigning nothing and " <>
            "has no public half to publish",
          true
        )
    end
  end
end
