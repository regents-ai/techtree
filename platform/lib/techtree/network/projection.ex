defmodule Techtree.Network.Projection do
  @moduledoc """
  What the read addresses say about a published run.

  This is a projection and not a bundle. Every member of it was recomputed from
  bytes that verified or copied out of a document whose signature was checked
  first, and none of it is the submitted bytes themselves — a public address
  returning the path-to-base64 file mapping hands over the whole bundle however
  it is wrapped in JSON, and decision 0038 defers that to a later release.
  The bytes are stored, immutably, and every field here is derived from them;
  they are simply not served.

  Two shapes, and the detail one is the list one with more in it, so a caller
  who has read a page of the log does not have to learn a second vocabulary to
  read one entry.

  The words are fixed. It is a **log sequence**, never a position, a rank or a
  place — a sequence is handed out in arrival order, may have gaps, and says
  nothing about how good a result is. There is no ordering here but arrival,
  and no argument that would produce one.

  A withdrawn entry appears exactly like any other, with `withdrawn_at` set. It
  keeps its sequence and it keeps its address, because withdrawal is an event
  appended to the log rather than a hole punched in it.
  """

  alias Techtree.Canonical
  alias Techtree.Network.PublicationEntry

  @list_schema_version "techtree.publication-log.v1alpha1"
  @entry_schema_version "techtree.publication-entry.v1alpha1"

  @doc """
  One page of the log, as the bytes `GET /api/v1/publications` returns.
  """
  @spec log(
          %{entries: [PublicationEntry.t()], next_before_sequence: pos_integer() | nil},
          String.t()
        ) ::
          binary()
  def log(%{entries: entries, next_before_sequence: next}, origin) do
    Canonical.encode!(%{
      "schema_version" => @list_schema_version,
      "entries" => Enum.map(entries, &summary(&1, origin)),
      "next_before_sequence" => next
    })
  end

  @doc """
  One entry, as the bytes `GET /api/v1/publications/:bundle_digest` returns.
  """
  @spec entry(PublicationEntry.t(), String.t()) :: binary()
  def entry(%PublicationEntry{} = entry, origin) do
    entry
    |> summary(origin)
    |> Map.merge(%{
      "schema_version" => @entry_schema_version,
      "task_deltas" => entry.task_deltas,
      "receipt" => %{
        "payload_digest" => entry.receipt_digest,
        "key_id" => entry.network_key_id
      }
    })
    |> Canonical.encode!()
  end

  @doc """
  The address one entry is read at by a person rather than by a program.
  """
  @spec entry_url(PublicationEntry.t(), String.t()) :: String.t()
  def entry_url(%PublicationEntry{bundle_digest: digest}, origin),
    do: origin <> "/results/" <> digest

  defp summary(%PublicationEntry{} = entry, origin) do
    %{
      "log_sequence" => entry.log_sequence,
      "bundle_digest" => entry.bundle_digest,
      "run_id" => entry.run_id,
      "accepted_at" => DateTime.to_iso8601(entry.accepted_at),
      "withdrawn_at" => entry.withdrawn_at && DateTime.to_iso8601(entry.withdrawn_at),
      "entry_url" => entry_url(entry, origin),
      "participant" => %{
        "kind" => to_string(entry.participant_kind),
        "key_id" => entry.participant_key_id,
        "public_key" => entry.participant_public_key
      },
      "climb" => entry.climb_reference,
      "campaign_spec_digest" => entry.campaign_spec_digest,
      "campaign_name" => entry.campaign_name,
      "data_policy_digest" => entry.data_policy_digest,
      "skill_digest" => entry.skill_digest,
      "skill_name" => entry.skill_name,
      "skill_github_url" => entry.skill_github_url,
      "subject" => %{
        "harness" => entry.subject_harness,
        "harness_version" => entry.subject_harness_version,
        "provider" => entry.subject_provider,
        "model" => entry.subject_model
      },
      "result" => %{
        "baseline_mean" => entry.baseline_mean,
        "candidate_mean" => entry.candidate_mean,
        "absolute_delta" => entry.absolute_delta,
        "wins" => entry.wins,
        "losses" => entry.losses,
        "ties" => entry.ties,
        "task_count" => entry.task_count
      },
      "statuses" => entry.statuses,
      "decision" => entry.decision,
      "proof_grade" => entry.proof_grade,
      "checks" => %{
        "run" => entry.verification_checks_run,
        "passed" => entry.verification_checks_passed
      }
    }
  end
end
