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
  the log rather than about the bundle.

  ## The retry is the case this module is built around

  The window is small and it is certain to happen: the server accepts, the
  response is lost on the way back, the participant's own command records the
  publication as failed, and a person runs it again. If the second attempt made
  a second row, the log would carry the same proof twice under two sequences,
  and the receipt the participant finally wrote down would not be the one this
  site had already issued.

  So idempotence is by bundle digest, and it is enforced by the database rather
  than by looking first. There is no "does this already exist" query in front of
  the insert, deliberately: a check like that is correct until two requests run
  it at the same moment, and then both of them insert. Instead every publication
  takes the same path — build the whole row, insert it, and if the unique index
  on `bundle_digest` refuses it, hand back the row that is already there. The
  loser of a race and the retry of a lost response are the same code, so the
  rare one is exercised by the common one.

  Four outcomes, and they are the four the founder named:

  * a bundle nobody has published is **recorded**, and the participant gets a
    fresh receipt;
  * the same bundle in the same document again is **existing**, and the
    participant gets back the original receipt, byte for byte, including its
    original log sequence and its original acceptance time;
  * the same bundle in a *different* document is a **conflict**: this log
    already stored one set of bytes under that digest and it will not quietly
    swap them for another;
  * the same participant and the same run under a *different* bundle is a
    **conflict** too, on a unique index over the two of them together. One run
    is published once. A second bundle for it is either a different run wearing
    the same name or the same run rebuilt, and either way the participant has to
    resolve it on their own machine rather than have this site pick.

  A participant may send an `Idempotency-Key` header if their tooling likes to.
  Nothing here reads one. The digest of the proof is the idempotence key, it is
  derived from the bytes rather than chosen by the sender, and a header would
  only add a second way to be wrong.

  ## Everything else

  *The log sequence is handed out by the database.* The log's order is arrival
  order, so it comes from a Postgres sequence rather than from counting rows.
  Two publications landing at the same instant get two sequences, and a
  publication that loses the race has already taken one, so the sequence has
  gaps. That is what a sequence is; a position would not be allowed to.

  *The row is written whole.* Its identifier, its sequence, its acceptance time
  and the receipt signed over all three go in together, so no reader can ever
  see an entry that does not yet have the receipt it was issued.

  *A withdrawal is written, not applied.* Taking an entry off the log appends a
  `withdrawn` event carrying the participant's own signature over their own
  withdrawal request, and writes the entry's `withdrawn_at` from it. The entry
  keeps every column it had and keeps its place, and no resource here offers a
  destroy action that could do otherwise.

  The one exception to that last rule is the contributor address, which is not
  evidence — it is something a person volunteered about themselves. Removing it
  removes it from the active system and from any future use. It is not a claim
  about database backups, which this release does not implement. It is keyed by
  the address rather than by a publication, so the same address left with two
  runs is one row carrying a count of two, and taking it away is one removal.

  It also never travels inside the submission. The bytes of a submission are
  stored, so an address written into them would be stored with the evidence
  however carefully everything downstream avoided printing it. It arrives beside
  them instead, is checked before anything else is done, and is written to a
  table nothing else in this application may read.
  """

  alias Techtree.Canonical
  alias Techtree.Catalog.Digest
  alias Techtree.Network
  alias Techtree.Network.Address
  alias Techtree.Network.Bundle
  alias Techtree.Network.ContributorAddress
  alias Techtree.Network.Error
  alias Techtree.Network.Key
  alias Techtree.Network.PublicationEntry
  alias Techtree.Network.PublicationEvent
  alias Techtree.Network.Receipt
  alias Techtree.Network.WithdrawalRequest
  alias Techtree.Repo

  @internal [authorize?: false]

  @typedoc """
  What happened to a publication that was not refused.
  """
  @type outcome :: :recorded | :existing

  @doc """
  Check one submission and, if every check holds, append it to the log.

  Returns `{:ok, entry, :recorded}` for a new entry and `{:ok, entry, :existing}`
  when this exact proof, in this exact document, is already published. Either
  way `entry.receipt_bytes` is the receipt to hand back.

  `:contributor_address` is the one thing a person may send that their machine
  did not sign. A wrong character in an address cannot be recovered from, so it
  is checked first and a submission carrying one that does not check out is
  refused rather than quietly published without it.

  `:origin` is where this site answers, which the receipt needs so that it can
  name the address the entry now lives at.
  """
  @spec accept(binary(), Key.t(), keyword()) ::
          {:ok, PublicationEntry.t(), outcome()} | {:error, Error.t()}
  def accept(raw, %Key{} = key, options \\ []) when is_binary(raw) do
    with {:ok, address} <- volunteered(Keyword.get(options, :contributor_address)),
         {:ok, metadata} <- metadata(options),
         {:ok, bundle} <- Bundle.verify(raw) do
      append(bundle, address, metadata, key, Keyword.get(options, :origin, ""))
    end
  end

  @doc """
  Take one published entry off the log, on the signed word of whoever published
  it.

  Returns `{:ok, entry, :recorded}` when this withdrawal was the one that
  marked it, and `{:ok, entry, :existing}` when it was already withdrawn — a
  retry of a lost response is not a second event.
  """
  @spec withdraw(binary()) :: {:ok, PublicationEntry.t(), outcome()} | {:error, Error.t()}
  def withdraw(raw) when is_binary(raw) do
    with {:ok, claimed} <- WithdrawalRequest.claimed_bundle_digest(raw),
         {:ok, entry} <- entry_named(claimed),
         {:ok, request} <- WithdrawalRequest.verify(raw, entry) do
      if is_nil(entry.withdrawn_at) do
        {:ok, mark_withdrawn(entry, request), :recorded}
      else
        {:ok, entry, :existing}
      end
    end
  end

  @doc """
  Forget an address somebody left, because they asked for it back.

  It goes from the active system and from any future use. It is not a claim
  about database backups. One address is one row however many publications
  supplied it, so this is one removal and there is no second copy of it
  anywhere to miss.
  """
  @spec forget_contributor_address(String.t()) :: :ok
  def forget_contributor_address(address) do
    case contributor_address(address) do
      nil -> :ok
      record -> Network.forget_contributor_address!(record, @internal)
    end

    :ok
  end

  @doc """
  The record for one address, for an operator answering a question about
  somebody's own record. Nothing on the public surface calls this, and nothing
  else in this application can.
  """
  @spec contributor_address(String.t()) :: ContributorAddress.t() | nil
  def contributor_address(address) do
    with {:ok, canonical} <- Address.canonicalize(address),
         {:ok, record} <- Network.get_contributor_address(canonical, @internal) do
      record
    else
      _other -> nil
    end
  end

  @doc """
  Everything appended against one entry, oldest first.
  """
  @spec events(PublicationEntry.t()) :: [PublicationEvent.t()]
  def events(%PublicationEntry{id: id}), do: Network.list_events_for_entry!(id, @internal)

  # -- The volunteered address ----------------------------------------------

  defp volunteered(nil), do: {:ok, nil}

  defp volunteered(value) do
    case Address.canonicalize(value) do
      {:ok, address} ->
        {:ok, address}

      {:error, :bad_checksum} ->
        {:error,
         Error.new(
           :contributor_address_invalid,
           "that address does not check out — one character of it is wrong, " <>
             "and an address with a wrong character in it cannot be recovered from"
         )}

      {:error, :malformed} ->
        {:error,
         Error.new(
           :contributor_address_invalid,
           "an address is 0x followed by exactly 40 hexadecimal characters"
         )}
    end
  end

  # These are public descriptive labels, not evidence. Keep the same narrow
  # label grammar used by the Skill preparation path, and only accept a
  # canonical repository URL so a projection never becomes a URL normalizer.
  defp metadata(options) do
    with {:ok, skill_name} <- skill_name(Keyword.get(options, :skill_name)),
         {:ok, skill_github_url} <- skill_github_url(Keyword.get(options, :skill_github_url)) do
      {:ok, %{skill_name: skill_name, skill_github_url: skill_github_url}}
    end
  end

  defp skill_name(nil), do: {:ok, nil}

  defp skill_name(value) when is_binary(value) do
    if Regex.match?(~r/^[A-Za-z0-9][A-Za-z0-9 ._-]{0,63}$/, value) do
      {:ok, value}
    else
      {:error,
       Error.new(
         :publication_skill_name_invalid,
         "a Skill name is up to 64 letters, digits, spaces, dots, dashes, or underscores, and starts with a letter or digit",
         %{"field" => "x-techtree-skill-name"}
       )}
    end
  end

  defp skill_name(_value), do: skill_name("")

  defp skill_github_url(nil), do: {:ok, nil}

  defp skill_github_url(value) when is_binary(value) do
    valid? =
      case URI.parse(value) do
        %URI{
          scheme: "https",
          authority: "github.com",
          host: "github.com",
          port: 443,
          userinfo: nil,
          query: nil,
          fragment: nil,
          path: "/" <> path
        } ->
          not String.ends_with?(path, ".git") and
            Regex.match?(
              ~r/^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$/,
              path
            )

        _other ->
          false
      end

    if valid? do
      {:ok, value}
    else
      {:error,
       Error.new(
         :publication_skill_github_url_invalid,
         "a Skill repository URL is a canonical HTTPS GitHub URL of the form https://github.com/owner/repository",
         %{"field" => "x-techtree-skill-github-url"}
       )}
    end
  end

  defp skill_github_url(_value), do: skill_github_url("")

  # -- Appending -------------------------------------------------------------

  defp append(%Bundle{} = bundle, address, metadata, key, origin) do
    appended =
      Ash.transact([PublicationEntry, PublicationEvent, ContributorAddress], fn ->
        entry =
          Network.record_publication_entry!(
            attributes(bundle, metadata, key, origin),
            @internal
          )

        Network.record_publication_event!(
          %{
            publication_entry_id: entry.id,
            kind: :accepted,
            payload_digest: entry.bundle_digest,
            participant_signature: Bundle.participant_signature(bundle)
          },
          @internal
        )

        remember(address, entry)
        entry
      end)

    case appended do
      {:ok, entry} ->
        {:ok, entry, :recorded}

      {:error, refusal} ->
        case conflict(bundle) do
          {:ok, answer} -> answer
          :unexplained -> raise refusal
        end
    end
  end

  # A publication the database refused is one of exactly three things, and
  # which one is answered by asking the log rather than by reading the error: a
  # retry of a publication that already went through, the same digest carrying
  # a different document, or a second bundle for a run that has already been
  # published. Anything else is a defect, and a defect is raised rather than
  # dressed up as a refusal.
  defp conflict(%Bundle{} = bundle) do
    digest = Bundle.digest(bundle)
    sent = submission_digest(bundle.raw)

    case Network.get_publication_entry_by_digest(digest, @internal) do
      {:ok, %PublicationEntry{submission_digest: ^sent} = entry} ->
        {:ok, {:ok, entry, :existing}}

      {:ok, %PublicationEntry{} = entry} ->
        {:ok,
         {:error,
          Error.new(
            :publication_bytes_conflict,
            "this log already holds a publication under that bundle digest, and " <>
              "it is not the document you just sent; stored bytes are never rewritten",
            %{"bundle_digest" => entry.bundle_digest, "log_sequence" => entry.log_sequence}
          )}}

      _other ->
        run_conflict(bundle)
    end
  end

  defp run_conflict(%Bundle{manifest: manifest}) do
    key_id = get_in(manifest, ["payload", "executor_identity", "key_id"])
    run_id = get_in(manifest, ["payload", "run_id"])

    case Network.get_publication_entry_by_run(key_id, run_id, @internal) do
      {:ok, %PublicationEntry{} = entry} ->
        {:ok,
         {:error,
          Error.new(
            :publication_run_conflict,
            "this key has already published that run, under a different bundle; " <>
              "one run is published once, and which bundle is the right one is " <>
              "yours to settle rather than ours to guess",
            %{
              "run_id" => entry.run_id,
              "bundle_digest" => entry.bundle_digest,
              "log_sequence" => entry.log_sequence
            }
          )}}

      _other ->
        :unexplained
    end
  end

  defp attributes(
         %Bundle{manifest: manifest, report: report, campaign: campaign} = bundle,
         metadata,
         key,
         origin
       ) do
    payload = manifest["payload"]
    identity = payload["executor_identity"]
    result = report["primary_result"]
    subject = get_in(campaign, ["agents", "subject"])

    entry = %{
      id: Ash.UUID.generate(),
      log_sequence: next_log_sequence(),
      accepted_at: DateTime.utc_now(),
      bundle_digest: Bundle.digest(bundle),
      submission_bytes: bundle.raw,
      submission_digest: submission_digest(bundle.raw),
      run_id: payload["run_id"],
      campaign_spec_digest: payload["campaign_spec_digest"],
      campaign_name: bundle.campaign_name,
      data_policy_digest: payload["data_policy_digest"],
      climb_reference: bundle.climb_reference,
      # The bundle check already refused anything that is not a local Ed25519
      # key, so this is the one kind rather than whatever the document said.
      participant_kind: :local_ed25519,
      participant_key_id: identity["key_id"],
      participant_public_key: identity["public_key"],
      subject_provider: get_in(subject, ["model", "provider"]),
      subject_model: get_in(subject, ["model", "model_id"]),
      subject_harness: get_in(subject, ["harness", "id"]),
      subject_harness_version: get_in(subject, ["harness", "version"]),
      skill_digest: bundle.candidate_skill_digest,
      skill_name: metadata.skill_name,
      skill_github_url: metadata.skill_github_url,
      baseline_mean: result["baseline_mean"] / 1,
      candidate_mean: result["candidate_mean"] / 1,
      absolute_delta: result["absolute_delta"] / 1,
      wins: result["wins"],
      losses: result["losses"],
      ties: result["ties"],
      task_count: length(report["task_deltas"]),
      statuses: report["statuses"] || %{},
      decision: report["decision"],
      proof_grade: report["proof_grade"],
      verification_checks_run: Bundle.check_count(),
      verification_checks_passed: Bundle.check_count(),
      task_deltas: report["task_deltas"],
      network_key_id: key.key_id
    }

    receipt = Receipt.issue(struct!(PublicationEntry, entry), origin, key)

    entry
    |> Map.put(:receipt_bytes, Receipt.encode(receipt))
    |> Map.put(:receipt_digest, Receipt.payload_digest(receipt))
  end

  # The log sequence is a database sequence rather than a count of rows,
  # because a count read inside one transaction is already stale in another.
  defp next_log_sequence do
    %{rows: [[sequence]]} = Repo.query!("SELECT nextval('network_publication_sequence')")
    sequence
  end

  # What tells a retry apart from a different document under the same digest.
  # It is the canonical form rather than the raw bytes, because the same
  # document written out with different whitespace is the same document, and a
  # participant whose tooling re-serialises before retrying has not sent
  # something else.
  defp submission_digest(raw) do
    case Jason.decode(raw) do
      {:ok, document} -> document |> Canonical.encode!() |> Digest.hash_bytes()
      _other -> Digest.hash_bytes(raw)
    end
  end

  defp remember(nil, _entry), do: :ok

  # Keyed by the address, so a publisher who leaves the same address with a
  # second run has one row with a count of two rather than a second row. The
  # pointer moves to the publication that most recently supplied it, which is
  # what a singular pointer beside a count can honestly mean.
  defp remember(address, entry) do
    Network.record_contributor_address!(
      %{address: address, publication_id: entry.id},
      @internal
    )

    :ok
  end

  # -- Withdrawing -----------------------------------------------------------

  defp entry_named(digest) do
    case Network.get_publication_entry_by_digest(digest, @internal) do
      {:ok, %PublicationEntry{} = entry} ->
        {:ok, entry}

      _other ->
        {:error,
         Error.new(
           :withdrawal_entry_missing,
           "no run is published under that fingerprint",
           %{"bundle_digest" => digest}
         )}
    end
  end

  defp mark_withdrawn(entry, %WithdrawalRequest{} = request) do
    {:ok, updated} =
      Ash.transact([PublicationEntry, PublicationEvent], fn ->
        event =
          Network.record_publication_event!(
            %{
              publication_entry_id: entry.id,
              kind: :withdrawn,
              payload_digest: request.payload_digest,
              participant_signature: request.signature
            },
            @internal
          )

        Network.mark_publication_entry_withdrawn!(
          entry,
          %{withdrawn_at: event.inserted_at},
          @internal
        )
      end)

    updated
  end
end
