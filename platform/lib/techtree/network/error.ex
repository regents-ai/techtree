defmodule Techtree.Network.Error do
  @moduledoc """
  The named ways a submission can be refused.

  A refusal has to say which check failed, and it has to say it in the shape
  every other refusal on this site already takes: a stable code a machine can
  branch on, a sentence that is safe to show a stranger, and whether trying
  again could possibly help. `Techtree.Catalog.Error` fixed that shape for the
  read surface; this is the same shape for the one address that reads a body.

  The codes are one-to-one with the checks in `Techtree.Network.Bundle`, so a
  participant whose bundle was turned away learns which property of it did not
  hold rather than that "verification failed". The details are limited to what
  the submitter already has: file paths inside their own bundle, digests they
  computed themselves, counts they can recount. Nothing about this site's
  machinery, and never anything the site knows and they do not.
  """

  @typedoc """
  Every reason a submission is not a row.
  """
  @type code ::
          :submission_too_large
          | :submission_malformed
          | :submission_artifact_missing
          | :submission_artifact_unlisted
          | :submission_artifact_digest_mismatch
          | :submission_payload_digest_mismatch
          | :submission_signature_invalid
          | :submission_key_id_mismatch
          | :submission_campaign_unpublished
          | :submission_counts_inconsistent
          | :submission_task_membership_mismatch
          | :contributor_address_invalid

  @type t :: %__MODULE__{
          code: code(),
          message: String.t(),
          retryable?: boolean(),
          details: %{optional(String.t()) => term()}
        }

  defexception [:code, :message, details: %{}, retryable?: false]

  @doc """
  Refuse a submission, naming the check that did not hold.
  """
  @spec new(code(), String.t(), map()) :: t()
  def new(code, message, details \\ %{}) do
    %__MODULE__{code: code, message: message, details: details, retryable?: false}
  end

  @doc """
  What each refusal means over HTTP.

  A body too large is refused by size, before anything about it is known. A
  body that is not a submission at all is a malformed request. Everything else
  is a well-formed request whose contents did not hold up, which is what `422`
  says.
  """
  @spec status_for(code()) :: 400 | 413 | 422
  def status_for(:submission_too_large), do: 413
  def status_for(:submission_malformed), do: 400
  def status_for(_code), do: 422
end
