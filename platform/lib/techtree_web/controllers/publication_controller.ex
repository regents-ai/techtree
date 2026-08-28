defmodule TechtreeWeb.PublicationController do
  @moduledoc """
  The one address a participant sends anything to, and the addresses that read
  the log back.

  A `POST` here is a participant saying something about their own run, and there
  are two things they may say. A `techtree.publication-submission.v1alpha1`
  publishes a finished run. A signed `techtree.publication-withdrawal.v1alpha1`
  withdraws one already published. Which arrived is read off the document —
  each declares what it is in a member its own signature covers — rather than
  off the URL, which is what lets this site keep the single write address
  decision 0038 allows it. `Techtree.Network.Document` does that reading and
  nothing else.

  Nothing about either is trusted. `Techtree.Network.Ingest` checks every
  property of a bundle before a row exists, and checks a withdrawal against the
  key the entry already carries before an event is appended; this controller's
  whole job is to hand over bytes, hand back a receipt, and name the check that
  failed when one did. It names the check rather than saying "invalid" because a
  participant whose bundle was turned away can only fix what they are told
  about, and every check here is one they can rerun on their own machine.

  Both receipts are signed envelopes — a payload, the digest of that payload's
  canonical bytes, and a detached signature over that digest — which is the
  shape every signed document in this protocol uses and the shape the
  participant's own tooling validates. `Techtree.Network.Receipt` builds them.

  Two gates stand in front of the checking, and both are here rather than in
  the verifier, because both are properties of the request rather than of the
  bundle. The body must arrive as `application/json` — anything else never
  reaches the parser that keeps the exact bytes, and is refused without being
  read. And the body is capped as it is read, which
  `TechtreeWeb.PublicationBody` does at the parser, before anything has been
  decoded or hashed.

  A `GET` here is the log, or one entry of it, as a **verified projection**.
  Every member of it was recomputed from bytes that verified or copied out of a
  document whose signature was checked first. It is not the submitted bytes: an
  address returning the path-to-base64 file mapping hands over the whole
  bundle however it is wrapped in JSON, and decision 0038 defers that to a
  later release. The bytes are stored, immutably, and everything published is
  derived from them; they are simply not served.

  The list is newest first by log sequence and by nothing else, one keyset page
  at a time — `?before_sequence=…&limit=…`, twenty-five by default and at most
  a hundred. There is no sort control, no offset, and no ordering a caller
  could ask for. A **log sequence** is not a position and not a rank: it is
  handed out in arrival order and it may have gaps.

  A withdrawn entry is still on the log and still at its own address, with
  `withdrawn_at` set. It was published and it is marked withdrawn, which is a
  different thing from never having existed and a different thing from being
  gone.

  One field arrives beside the body rather than in it. A publisher may
  volunteer an address to be recognised by later, and it is read from
  `x-techtree-contributor-address` precisely because the body is stored: an
  address inside the body would be stored with the evidence. The header is not
  echoed, not stored with the entry, and not readable from anywhere on the
  public surface. Nothing is offered in exchange for one.

  What comes back on acceptance is a `techtree.publication-receipt.v1alpha1`
  payload signed by this site's own key: the participant signed their run, and
  this is the network signing that it accepted it. A withdrawal comes back as a
  `techtree.publication-withdrawal-receipt.v1alpha1` payload in the same
  envelope, naming where the entry still lives rather than saying it is gone.
  `Techtree.Network.Key` holds the key, and it is loaded before the body is read
  rather than after anything is written, because this address owes a receipt for
  what it accepts — so a build that cannot countersign refuses outright instead
  of recording something it cannot answer for. The participant can send the
  identical document again once the key is there.
  """

  use TechtreeWeb, :controller

  alias Techtree.Catalog.Digest
  alias Techtree.Network.Document
  alias Techtree.Network.Error
  alias Techtree.Network.Ingest
  alias Techtree.Network.Key
  alias Techtree.Network.Projection
  alias Techtree.Network.Query
  alias Techtree.Network.Receipt
  alias TechtreeWeb.ExactResponse

  @doc """
  Publish one finished run, or withdraw one already published.
  """
  def create(conn, _params) do
    case conn.assigns[:submitted_bytes] do
      bytes when is_binary(bytes) -> received(conn, bytes)
      nil -> refuse_content_type(conn)
    end
  end

  @doc """
  One page of the log, newest arrival first.
  """
  def index(conn, params) do
    case Query.read_page_options(params) do
      {:ok, options} ->
        bytes = Projection.log(Query.page(options), origin())

        ExactResponse.send_exact(
          conn,
          bytes,
          "application/json",
          Digest.hash_bytes(bytes),
          :no_store
        )

      {:error, message} ->
        ExactResponse.send_error(conn, 400, :publication_query_invalid, message, false)
    end
  end

  @doc """
  One published run, as everything this site is willing to say about it.
  """
  def show(conn, %{"bundle_digest" => digest}) do
    with true <- Digest.valid?(digest),
         {:ok, entry} <- Query.get_entry(digest) do
      bytes = Projection.entry(entry, origin())

      ExactResponse.send_exact(
        conn,
        bytes,
        "application/json",
        Digest.hash_bytes(bytes),
        :no_store
      )
    else
      _other ->
        ExactResponse.send_error(
          conn,
          404,
          :publication_missing,
          "no run is published under that fingerprint",
          false
        )
    end
  end

  defp received(conn, bytes) do
    with {:ok, kind} <- Document.kind(bytes),
         {:ok, key} <- countersigning_key() do
      case kind do
        :submission -> record(conn, bytes, key)
        :withdrawal -> withdraw(conn, bytes, key)
      end
    else
      {:error, %Error{} = error} -> refuse(conn, error)
      :error -> refuse_uncountersignable(conn)
    end
  end

  defp countersigning_key, do: Key.load()

  defp record(conn, bytes, key) do
    accepted =
      Ingest.accept(bytes, key,
        contributor_address: volunteered(conn),
        origin: origin()
      )

    case accepted do
      {:ok, entry, :recorded} -> receipt(conn, entry, 201)
      {:ok, entry, :existing} -> receipt(conn, entry, 200)
      {:error, %Error{} = error} -> refuse(conn, error)
    end
  end

  # A withdrawal is answered with its own countersigned envelope rather than
  # with the entry's projection, so that the participant has a signed record of
  # the thing they asked for, checkable against the same key as their receipt.
  # It is built for this response rather than stored, because the entry it
  # describes carries the date it is about: two withdrawals of the same entry
  # produce the same document.
  defp withdraw(conn, bytes, key) do
    case Ingest.withdraw(bytes) do
      {:ok, entry, _outcome} ->
        sent =
          entry
          |> Receipt.issue_withdrawal(origin(), key)
          |> Receipt.encode()

        conn
        |> put_resp_content_type("application/json")
        |> put_resp_header("cache-control", "no-store")
        |> send_resp(200, sent)

      {:error, %Error{} = error} ->
        refuse(conn, error)
    end
  end

  # What the network says back: where the entry landed, which checks ran, the
  # address the entry now lives at, and this site's signature over all of it.
  # It is the receipt stored on the row rather than one built for this
  # response, so a retry after a lost response is handed the original.
  defp receipt(conn, entry, status) do
    # Built by hand rather than with the route sigil: a digest carries a colon,
    # and the sigil would escape it into an address nobody could read back.
    location = "/api/v1/publications/" <> entry.bundle_digest

    conn
    |> put_resp_content_type("application/json")
    |> put_resp_header("cache-control", "no-store")
    |> put_resp_header("location", location)
    |> send_resp(status, entry.receipt_bytes)
  end

  defp volunteered(conn) do
    case get_req_header(conn, "x-techtree-contributor-address") do
      [address | _rest] -> address
      [] -> nil
    end
  end

  defp origin, do: TechtreeWeb.Endpoint.url()

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
      "what this address takes is sent as application/json, at most " <>
        "#{Techtree.Network.maximum_body_bytes()} bytes: the files of one proof " <>
        "bundle, or a signed request to withdraw one already published",
      false
    )
  end
end
