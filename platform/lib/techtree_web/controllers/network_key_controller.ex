defmodule TechtreeWeb.NetworkKeyController do
  @moduledoc """
  The public half of the key this site countersigns publications with.

  A publication receipt carries a signature and the fingerprint of the key that
  made it. That is only checkable if the key itself is somewhere fixed, so it is
  here: `GET /api/v1/network-key`, one stable address, no parameters, nothing
  to look up. Somebody holding a receipt — including somebody who trusts
  neither the participant nor this site — fetches this, checks that the
  fingerprint is the hash of the key, and verifies the signature over the
  receipt's own canonical digest. `Techtree.Network.Receipt` documents that
  procedure from the other end.

  What is served is exactly the three-member public key document this protocol
  writes every key as, in canonical form and nothing more, because the
  participant's own tooling validates it as that document and refuses one
  carrying anything else.

  A build with no key configured answers `503` rather than serving a placeholder
  or an empty document. There is no key to publish, and saying so is the only
  honest answer; `Techtree.Network.Key` says why a key is never invented to fill
  the gap.
  """

  use TechtreeWeb, :controller

  alias Techtree.Canonical
  alias Techtree.Catalog.Digest
  alias Techtree.Network.Key
  alias TechtreeWeb.ExactResponse

  @doc """
  Return the network's public signing key.
  """
  def show(conn, _params) do
    case Key.load() do
      {:ok, key} ->
        bytes = Canonical.encode!(Key.reference(key))

        ExactResponse.send_exact(
          conn,
          bytes,
          "application/json",
          Digest.hash_bytes(bytes),
          :revalidated
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
