defmodule Techtree.Network.Ingest do
  @moduledoc """
  The only thing in this application that writes to the run log.

  Every resource in `Techtree.Network` forbids create, update and destroy
  through any interface, so a page, a console, a live transport or a future
  endpoint cannot write one however it is asked. This module is the single
  exception, and it bypasses authorization in the same explicit way
  `Techtree.Catalog.Importer` does — deliberately, and in one place a reader can
  find and audit.

  Nothing here decides whether a submission is good. That is
  `Techtree.Network.Bundle`'s job, and it happens first, in full, before a row
  exists. What is left for this module is the part that has to be true about
  the log rather than about the bundle:

  *Position is handed out by the database.* The log's order is arrival order, so
  the position comes from a Postgres sequence rather than from counting rows.
  Two submissions landing at the same instant get two positions.

  *The same bundle is the same entry.* A proof's digest is a content address, so
  sending the same proof twice is not two publications — the second call returns
  the entry that already exists. That is what a content-addressed log means, not
  a leniency about duplicates.

  *A withdrawal is written, not applied.* Taking an entry off the log appends a
  withdrawal row and writes the entry's `withdrawn_at` from it. The entry keeps
  every column it had, and no resource here offers a destroy action that could
  do otherwise.

  The one exception to that last rule is the contributor address, which is not
  evidence — it is something a person volunteered about themselves. Removing it
  removes it.

  It also never travels inside the submission. The bytes of a submission are
  stored and served back at a public address, so an address written into them
  would be a public address by construction, however carefully everything
  downstream avoided printing it. It arrives beside them instead, is checked
  before anything else is done, and is written to a table nothing public can
  read.
  """

  alias Techtree.Network
  alias Techtree.Network.Address
  alias Techtree.Network.Bundle
  alias Techtree.Network.ContributorAddress
  alias Techtree.Network.Submission
  alias Techtree.Network.Withdrawal
  alias Techtree.Repo

  @internal [authorize?: false]

  @doc """
  Check one submission and, if every check holds, append it to the log.

  Returns `{:ok, entry, :recorded}` for a new entry and `{:ok, entry, :existing}`
  when this exact proof is already published.

  `:contributor_address` is the one thing a person may send that their machine
  did not sign. A wrong character in an address cannot be recovered from, so it
  is checked first and a submission carrying one that does not check out is
  refused rather than quietly published without it.
  """
  @spec accept(binary(), keyword()) ::
          {:ok, Submission.t(), :recorded | :existing} | {:error, Network.Error.t()}
  def accept(raw, options \\ []) when is_binary(raw) do
    with {:ok, address} <- volunteered(Keyword.get(options, :contributor_address)),
         {:ok, bundle} <- Bundle.verify(raw) do
      case Network.get_submission_by_digest(Bundle.digest(bundle), @internal) do
        {:ok, %Submission{} = existing} -> {:ok, existing, :existing}
        _other -> {:ok, append(bundle, address), :recorded}
      end
    end
  end

  defp volunteered(nil), do: {:ok, nil}

  defp volunteered(value) do
    case Address.canonicalize(value) do
      {:ok, address} ->
        {:ok, address}

      {:error, :bad_checksum} ->
        {:error,
         Network.Error.new(
           :contributor_address_invalid,
           "that address does not check out — one character of it is wrong, " <>
             "and an address with a wrong character in it cannot be recovered from"
         )}

      {:error, :malformed} ->
        {:error,
         Network.Error.new(
           :contributor_address_invalid,
           "an address is 0x followed by exactly 40 hexadecimal characters"
         )}
    end
  end

  @doc """
  Take one published entry off the log by appending a withdrawal against it.
  """
  @spec withdraw(Submission.t(), atom()) :: Submission.t()
  def withdraw(%Submission{} = submission, reason) do
    {:ok, updated} =
      Ash.transact([Submission, Withdrawal], fn ->
        withdrawal =
          Network.record_withdrawal!(%{submission_id: submission.id, reason: reason}, @internal)

        Network.mark_submission_withdrawn!(
          submission,
          %{withdrawn_at: withdrawal.inserted_at},
          @internal
        )
      end)

    updated
  end

  @doc """
  Forget an address somebody left, because they asked for it back.
  """
  @spec forget_contributor_address(String.t()) :: :ok
  def forget_contributor_address(address) do
    case Network.get_contributor_address(address, @internal) do
      {:ok, %ContributorAddress{} = record} ->
        Network.forget_contributor_address!(record, @internal)
        :ok

      _other ->
        :ok
    end
  end

  @doc """
  The address one publisher left, for an operator answering a question about
  their own record. Nothing on the public surface calls this.
  """
  @spec contributor_address(String.t()) :: ContributorAddress.t() | nil
  def contributor_address(address) do
    case Network.get_contributor_address(address, @internal) do
      {:ok, %ContributorAddress{} = record} -> record
      _other -> nil
    end
  end

  # -- Internals ------------------------------------------------------------

  defp append(%Bundle{} = bundle, address) do
    {:ok, submission} =
      Ash.transact([Submission, ContributorAddress], fn ->
        submission = Network.record_submission!(attributes(bundle), @internal)
        remember(address, submission)
        submission
      end)

    submission
  end

  defp attributes(%Bundle{manifest: manifest, report: report, campaign: campaign} = bundle) do
    payload = manifest["payload"]
    identity = payload["executor_identity"]
    result = report["primary_result"]
    subject = get_in(campaign, ["agents", "subject"])

    %{
      sequence: next_sequence(),
      bundle_digest: Bundle.digest(bundle),
      run_id: payload["run_id"],
      campaign_spec_digest: payload["campaign_spec_digest"],
      data_policy_digest: payload["data_policy_digest"],
      climb_reference: bundle.climb_reference,
      # The bundle check already refused anything that is not a local Ed25519
      # key, so this is the one kind rather than whatever the document said.
      executor_kind: :local_ed25519,
      executor_key_id: identity["key_id"],
      executor_public_key: identity["public_key"],
      subject_model: get_in(subject, ["model", "model_id"]),
      subject_harness: get_in(subject, ["harness", "id"]),
      subject_harness_version: get_in(subject, ["harness", "version"]),
      baseline_mean: result["baseline_mean"] / 1,
      candidate_mean: result["candidate_mean"] / 1,
      absolute_delta: result["absolute_delta"] / 1,
      wins: result["wins"],
      losses: result["losses"],
      ties: result["ties"],
      task_count: length(report["task_deltas"]),
      decision: report["decision"],
      proof_grade: report["proof_grade"],
      verification_checks_run: Bundle.check_count(),
      verification_checks_passed: Bundle.check_count(),
      task_deltas: report["task_deltas"],
      raw_payload: bundle.raw
    }
  end

  # The log position is a database sequence rather than a count of rows,
  # because a count read inside one transaction is already stale in another.
  defp next_sequence do
    %{rows: [[sequence]]} = Repo.query!("SELECT nextval('network_submission_sequence')")
    sequence
  end

  defp remember(nil, _submission), do: :ok

  defp remember(address, submission) do
    now = DateTime.utc_now()
    seen = Network.get_contributor_address(address, @internal)

    count =
      case seen do
        {:ok, %ContributorAddress{submission_count: count}} -> count + 1
        _other -> 1
      end

    first =
      case seen do
        {:ok, %ContributorAddress{first_seen_at: at}} -> at
        _other -> now
      end

    Network.record_contributor_address!(
      %{
        address: address,
        submission_id: submission.id,
        submission_count: count,
        first_seen_at: first,
        last_seen_at: now
      },
      @internal
    )

    :ok
  end
end
