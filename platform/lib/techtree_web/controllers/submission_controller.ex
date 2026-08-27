defmodule TechtreeWeb.SubmissionController do
  @moduledoc """
  The one address on this site that accepts something, and the address that
  gives it back.

  A `POST` here is a participant publishing a finished run. Nothing about it is
  trusted: `Techtree.Network.Ingest` checks every property of the bundle before
  a row exists, and this controller's whole job is to hand over bytes, hand back
  a receipt, and name the check that failed when one did. It names the check
  rather than saying "invalid" because a participant whose bundle was turned
  away can only fix what they are told about, and every check here is one they
  can rerun on their own machine.

  A `GET` here is the same submission, byte for byte, at the address the log
  entry lives at. It is served the way every other exact-byte address on this
  site is served — the media type recorded, an entity tag that is what the
  bytes hash to, and a caching rule that says a content address never changes —
  so that anybody can fetch a published run and redo all eight checks offline
  without taking this site's word for any of them.

  A withdrawn entry is `410`. It was published, it is not published now, and
  that is a different thing from never having existed.

  One field arrives beside the body rather than in it. A publisher may
  volunteer an address to be recognised by later, and it is read from
  `x-techtree-contributor-address` precisely because the body is stored and
  served back: anything inside the body is public by construction. The header
  is not echoed, not stored with the entry, and not readable from anywhere on
  the public surface. Nothing is offered in exchange for one.

  What comes back on acceptance is a `techtree.publication-receipt.v1alpha1`
  document, signed by this site's own key: the participant signed their run,
  and this is the network signing that it accepted it.
  `Techtree.Network.Receipt` builds it and `Techtree.Network.Key` holds the key.
  The key is loaded before the body is read rather than after the entry is
  written, because this address owes a receipt for what it accepts, so a build
  that cannot countersign refuses the publication outright instead of appending
  a run it cannot answer for. The participant can publish the identical bundle
  again once the key is there.
  """

  use TechtreeWeb, :controller

  alias Techtree.Catalog.Digest
  alias Techtree.Network.Error
  alias Techtree.Network.Ingest
  alias Techtree.Network.Key
  alias Techtree.Network.Query
  alias Techtree.Network.Receipt
  alias TechtreeWeb.ExactResponse

  @doc """
  Publish one finished run, if every check holds.
  """
  def create(conn, _params) do
    case conn.assigns[:submitted_bytes] do
      bytes when is_binary(bytes) -> record(conn, bytes)
      nil -> refuse_content_type(conn)
    end
  end

  @doc """
  Return the exact bytes one published entry was submitted as.
  """
  def show(conn, %{"digest" => digest}) do
    with true <- Digest.valid?(digest),
         {:ok, entry} <- Query.get_entry(digest) do
      if Query.withdrawn?(entry) do
        ExactResponse.send_error(
          conn,
          410,
          :submission_withdrawn,
          "this entry was withdrawn from the log",
          false
        )
      else
        ExactResponse.send_exact(
          conn,
          entry.raw_payload,
          "application/json",
          Digest.hash_bytes(entry.raw_payload),
          :immutable
        )
      end
    else
      _other ->
        ExactResponse.send_error(
          conn,
          404,
          :submission_missing,
          "no run is published under that fingerprint",
          false
        )
    end
  end

  defp record(conn, bytes) do
    case Key.load() do
      {:ok, key} -> record(conn, bytes, key)
      :error -> refuse_uncountersignable(conn)
    end
  end

  defp record(conn, bytes, key) do
    case Ingest.accept(bytes, contributor_address: volunteered(conn)) do
      {:ok, entry, :recorded} -> receipt(conn, entry, key, 201)
      {:ok, entry, :existing} -> receipt(conn, entry, key, 200)
      {:error, %Error{} = error} -> refuse(conn, error)
    end
  end

  # What the network says back: where the entry landed, which checks ran, the
  # address the entry now lives at, and this site's signature over all of it.
  # The participant signed their run; this is the network countersigning that it
  # accepted it.
  defp receipt(conn, entry, key, status) do
    # Built by hand rather than with the route sigil: a digest carries a colon,
    # and the sigil would escape it into an address nobody could read back.
    location = "/api/v1/submissions/" <> entry.bundle_digest
    entry_url = TechtreeWeb.Endpoint.url() <> "/network/" <> entry.bundle_digest

    conn
    |> put_resp_content_type("application/json")
    |> put_resp_header("cache-control", "no-store")
    |> put_resp_header("location", location)
    |> send_resp(status, Receipt.encode(Receipt.issue(entry, entry_url, key)))
  end

  defp volunteered(conn) do
    case get_req_header(conn, "x-techtree-contributor-address") do
      [address | _rest] -> address
      [] -> nil
    end
  end

  defp refuse(conn, %Error{} = error) do
    ExactResponse.send_error(
      conn,
      Error.status_for(error.code),
      error.code,
      error.message,
      error.retryable?
    )
  end

  defp refuse_uncountersignable(conn) do
    ExactResponse.send_error(
      conn,
      503,
      :network_key_unavailable,
      "this site countersigns every run it publishes and cannot countersign " <>
        "one right now, so it is not accepting one; the same bundle can be " <>
        "published again unchanged",
      true
    )
  end

  defp refuse_content_type(conn) do
    ExactResponse.send_error(
      conn,
      400,
      :submission_malformed,
      "a published run is sent as application/json, at most " <>
        "#{Techtree.Network.maximum_body_bytes()} bytes, carrying the files of one proof bundle",
      false
    )
  end
end
