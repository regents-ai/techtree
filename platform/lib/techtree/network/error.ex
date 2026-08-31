defmodule Techtree.Network.Error do
  @moduledoc """
  The named ways a submission can be refused.

  A refusal has to say which check failed, and it has to say it in the shape
  every other refusal on this site already takes: a stable code a machine can
  branch on, a sentence that is safe to show a stranger, and whether trying
  again could possibly help. `Techtree.Catalog.Error` fixed that shape for the
  read surface; this is the same shape for the two addresses that read a body.

  Most of the codes are one-to-one with the checks in
  `Techtree.Network.Bundle`; two more name the two claims the submission
  document makes about the bundle it carries, which are refused when they
  disagree with it, and three name the ways one already-published entry can
  conflict with a new one. Either way a participant whose bundle was turned
  away learns which property of it did not hold rather than that "verification
  failed". The details are limited to what the submitter already has: file
  paths inside their own bundle, digests they computed themselves, counts they
  can recount. Nothing about this site's machinery, and never anything the site
  knows and they do not.
  """

  @typedoc """
  Every reason a submission is not a row.
  """
  @type code ::
          :submission_too_large
          | :submission_malformed
          | :submission_too_many_files
          | :submission_path_invalid
          | :submission_file_empty
          | :submission_file_not_canonical_base64
          | :submission_manifest_missing
          | :submission_artifact_missing
          | :submission_artifact_unlisted
          | :submission_artifact_digest_mismatch
          | :submission_payload_digest_mismatch
          | :submission_signature_invalid
          | :submission_key_id_mismatch
          | :submission_report_missing
          | :submission_campaign_unpublished
          | :submission_counts_inconsistent
          | :submission_task_membership_mismatch
          | :submission_data_policy_forbids_publication
          | :submission_private_content
          | :submission_bundle_digest_mismatch
          | :submission_run_id_mismatch
          | :contributor_address_invalid
          | :publication_skill_name_invalid
          | :publication_skill_github_url_invalid
          | :publication_bytes_conflict
          | :publication_run_conflict
          | :withdrawal_malformed
          | :withdrawal_signature_invalid
          | :withdrawal_entry_missing

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
  body that is not a submission at all is a malformed request. A submission
  that disagrees with something this log already holds is a conflict, and
  naming it `409` is what lets a participant's own tooling tell "you already
  published this" apart from "your bundle is wrong". A withdrawal naming an
  entry that is not here is a `404`. Everything else is a well-formed request
  whose contents did not hold up, which is what `422` says.
  """
  @spec status_for(code()) :: 400 | 404 | 409 | 413 | 422
  def status_for(:submission_too_large), do: 413
  def status_for(:submission_malformed), do: 400
  def status_for(:withdrawal_malformed), do: 400
  def status_for(:withdrawal_entry_missing), do: 404
  def status_for(:publication_bytes_conflict), do: 409
  def status_for(:publication_run_conflict), do: 409
  def status_for(_code), do: 422
end
