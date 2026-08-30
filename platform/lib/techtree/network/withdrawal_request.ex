defmodule Techtree.Network.WithdrawalRequest do
  @moduledoc """
  A participant asking for their own published run to be marked withdrawn, and
  proving it is theirs to ask about.

  Withdrawal is a right the founder ruled on before anybody asked for it: a
  published entry is withdrawn, never deleted, and a public promise with no
  executable path would be worse than neither. So this exists rather than a
  sentence saying it could.

  ## The document

  Fixed by `techtree-python/schemas/v1alpha1/publication-withdrawal.schema.json`
  and built against that file rather than against anybody's description of it.
  It is the signed envelope every document in this protocol is written as,
  carrying a payload of exactly three members:

  ```json
  {
    "payload": {
      "schema_version": "techtree.publication-withdrawal.v1alpha1",
      "bundle_digest": "sha256:<64 hex>",
      "requested_at": "<RFC 3339, UTC>"
    },
    "payload_digest": "sha256:<canonical digest of payload>",
    "signature": {
      "algorithm": "ed25519",
      "key_id": "sha256:<64 hex>",
      "signature": "<base64>"
    }
  }
  ```

  There is no reason field and there will not be one: nothing a submitter writes
  reaches this site. There is no public key in the request either, and that
  absence is the design. The network already holds the participant's key inside
  the bundle it accepted, and looking it up there rather than believing one that
  arrived with the request is what makes the signature mean anything.

  ## What is checked, and in what order

  1. The body is a signed envelope with the three envelope members.
  2. The payload has exactly the three members above, and the schema version is
     the withdrawal one.
  3. The payload digest is the digest of the payload's own canonical form,
     recomputed here.
  4. The bundle digest names an entry this log holds. That is the only thing
     read out of the request before anything is proven, and it is read to find
     the entry rather than to trust it. A signed document names its own subject,
     and taking the subject from a URL instead would be a second source of truth
     for the one fact the signature is over — which is also why this arrives at
     the same address a submission does, with no path parameter at all.
  5. The signature verifies as Ed25519 over that digest, under the public key
     **the entry already carries** — not under a key the request supplies, and
     not under one the request's own `key_id` names. That is the whole of the
     authorisation: the only person who can withdraw a run is whoever holds the
     key that published it, and a request naming any other fingerprint is
     refused by the same check for the same reason, because a signature that
     verifies under the entry's key could only have been made with it.
  6. `requested_at` is a time. It is the participant's own account of when they
     decided, and it is checked for shape and then not used to date anything:
     the log records when the log recorded it, the way it records when the log
     accepted the run, because a date on a public page that a submitter chose is
     a date a submitter chose.
  """

  alias Techtree.Canonical
  alias Techtree.Catalog.Digest
  alias Techtree.Network.Error
  alias Techtree.Network.PublicationEntry

  @schema_version "techtree.publication-withdrawal.v1alpha1"
  @envelope_keys ~w(payload payload_digest signature)
  @payload_keys ~w(bundle_digest requested_at schema_version)

  defstruct [:bundle_digest, :payload_digest, :signature]

  @type t :: %__MODULE__{
          bundle_digest: String.t(),
          payload_digest: String.t(),
          signature: String.t()
        }

  @doc """
  The schema version a withdrawal request declares, which is how one is told
  apart from a submission at the address they share.
  """
  @spec schema_version() :: String.t()
  def schema_version, do: @schema_version

  @doc """
  The bundle digest a request names, before anything about it has been proven.

  The caller needs this to find the entry whose key the signature is then
  checked against. It proves nothing on its own and is used for nothing else.
  """
  @spec claimed_bundle_digest(binary()) :: {:ok, String.t()} | {:error, Error.t()}
  def claimed_bundle_digest(raw) when is_binary(raw) do
    with {:ok, envelope} <- envelope(raw),
         {:ok, payload} <- payload(envelope) do
      {:ok, payload["bundle_digest"]}
    end
  end

  @doc """
  Check one withdrawal request against the entry it names.
  """
  @spec verify(binary(), PublicationEntry.t()) :: {:ok, t()} | {:error, Error.t()}
  def verify(raw, %PublicationEntry{} = entry) when is_binary(raw) do
    with {:ok, envelope} <- envelope(raw),
         {:ok, payload} <- payload(envelope),
         :ok <- recomputed(payload, envelope["payload_digest"]),
         :ok <- signed_by_the_publisher(envelope, entry) do
      {:ok,
       %__MODULE__{
         bundle_digest: payload["bundle_digest"],
         payload_digest: envelope["payload_digest"],
         signature: envelope["signature"]["signature"]
       }}
    end
  end

  defp envelope(raw) do
    with {:ok, decoded} <- Jason.decode(raw),
         true <- is_map(decoded),
         true <- Enum.sort(Map.keys(decoded)) == @envelope_keys,
         true <- is_binary(decoded["payload_digest"]),
         true <- is_map(decoded["signature"]) do
      {:ok, decoded}
    else
      _other -> {:error, malformed()}
    end
  end

  defp payload(%{"payload" => payload}) do
    with true <- is_map(payload),
         true <- Enum.sort(Map.keys(payload)) == @payload_keys,
         @schema_version <- payload["schema_version"],
         true <- Digest.valid?(payload["bundle_digest"]),
         {:ok, _time, _offset} <- DateTime.from_iso8601(to_string(payload["requested_at"])) do
      {:ok, payload}
    else
      _other -> {:error, malformed()}
    end
  end

  defp recomputed(payload, claimed) do
    case Canonical.encode(payload) do
      {:ok, canonical} ->
        if Digest.hash_bytes(canonical) == claimed do
          :ok
        else
          {:error,
           Error.new(
             :withdrawal_malformed,
             "this request does not hash to the digest written beside it, so " <>
               "the signature is not over what it carries",
             %{"claimed_digest" => claimed, "computed_digest" => Digest.hash_bytes(canonical)}
           )}
        end

      {:error, _reason} ->
        {:error, malformed()}
    end
  end

  defp signed_by_the_publisher(envelope, entry) do
    %{"payload_digest" => digest, "signature" => signature} = envelope

    with %{"algorithm" => "ed25519", "signature" => encoded} <- signature,
         {:ok, raw} when byte_size(raw) == 64 <- Base.decode64(encoded),
         {:ok, key} when byte_size(key) == 32 <- Base.decode64(entry.participant_public_key),
         true <- :crypto.verify(:eddsa, :none, digest, raw, [key, :ed25519]) do
      :ok
    else
      _other ->
        {:error,
         Error.new(
           :withdrawal_signature_invalid,
           "a run is withdrawn by whoever published it, and this request is not " <>
             "signed by the key that entry carries",
           %{"key_id" => entry.participant_key_id}
         )}
    end
  end

  defp malformed do
    Error.new(
      :withdrawal_malformed,
      "a withdrawal is a signed #{@schema_version} document naming the bundle " <>
        "digest of the run it withdraws and when it was asked for, and nothing else"
    )
  end
end
