defmodule Techtree.Network.Bundle do
  @moduledoc """
  Everything that has to hold before a submission is allowed to become a row.

  A published entry says, in effect, "this site checked this". The only way for
  that sentence to be worth anything is for the checking to happen before the
  row exists, in one place, with no path around it — so this module takes bytes
  and returns either a fully checked bundle or the name of the first check that
  did not hold. `Techtree.Network.Ingest` cannot write without one, and there
  is no other way to get one.

  Seventeen checks run, in the order below, and each of them refuses a
  different lie. Eight of them — the ones marked *proof* — are the ones the
  founder settled on as the verification depth of this service. The rest are
  admission checks: they are about what this site is willing to store and serve
  at a public address, not about whether the proof holds together.

    1. **Size.** The body is under a hard cap. A proof bundle has no
       transcripts in it and is a few hundred kilobytes; anything much larger
       is not one.
    2. **The document.** Exactly four members — the schema version, the run,
       the bundle's digest, and the files — with nothing else and nothing
       repeated. Those bytes are stored, so a document that allowed anything
       beside the proof would be a way to have this site keep whatever somebody
       wanted to put in it. `files` is a mapping of path to base64 and nothing
       else: it carries no per-file digest and no per-file size, because those
       would be claims the submitter wrote, and every digest here is taken from
       the bundle's own signed manifest instead.
    3. **The file count.** A proof bundle for this Climb is under a hundred
       files. The cap is generous and it is still a cap, because a mapping with
       no ceiling is a way to spend this site's memory before any digest has
       been computed.
    4. **The paths.** Every key is one relative POSIX path inside the bundle,
       spelled once. No absolute path, no `..`, no `.`, no backslash, no empty
       segment, no repetition — a path that can be written two ways is a file
       that can be swapped after it was checked.
    5. **The bytes.** Every file is canonical base64 — decoded and re-encoded
       to the identical string, so no second spelling of the same bytes exists
       — and no file is empty. An empty file is not a document, and it is not
       what any artifact list here describes.
    6. **The manifest.** The bundle carries a signed `bundle.json` at its root.
       Everything after this is read out of it.
    7. *Proof.* Every file hashes to the digest the bundle's own artifact list
       claims for it, and the bundle carries exactly the files that list names
       — no fewer, so nothing is missing, and no more, so nothing rode along
       unaccounted for.
    8. *Proof.* Every signed envelope's `payload_digest` is the digest of its
       payload's canonical form, recomputed here. A digest written beside the
       thing it describes proves nothing on its own.
    9. *Proof.* Every signature verifies as Ed25519 over that digest, under the
       public key the bundle carries. What is signed is the digest string
       itself, so a verifier needs only the digest and the key.
   10. *Proof.* The key's fingerprint is the hash of the key. It is derived, not
       asserted, so a bundle cannot claim somebody else's identifier.
   11. **The report.** The bundle carries the signed result summary its own
       manifest commits to. A manifest naming a report it does not carry is a
       bundle with nothing to publish.
   12. *Proof.* The Campaign the run names is one this site publishes. This is
       the check that makes spam uninteresting: a submission has to be a run of
       a comparison we defined, against tasks we committed to in advance, and
       there is nothing to gain by sending anything else.
   13. *Proof.* The report's wins, losses and ties recompute from its own task
       rows.
   14. *Proof.* Those task rows are the Campaign's committed task list, in the
       same order, exactly — not a subset, not a superset, not a reordering.
   15. **The terms.** The DataPolicy the run cites is carried in the bundle and
       permits exactly this: a public uplift report and public aggregate
       scores. A run carried out under terms that do not permit publication is
       refused rather than published against its owner's own stated wishes.
   16. **The content.** No submitted file carries a raw episode, a transcript, a
       prompt, a reply, a worker log, or a path on somebody's own machine. The
       proof format has nowhere to put one, which is exactly why a submission
       carrying one is not a proof bundle and is not stored here.
   17. *Proof.* What the submission claims about the bundle is what the bundle
       says. `run_id` and `bundle_digest` are read for nothing else — every
       column the site records comes from the signed bytes — but a submission
       whose declared digest is not the manifest's own payload digest, or whose
       declared run is not the one the signed report names, is refused rather
       than quietly published under the bundle's version of events. It runs
       last, because "what the bundle itself says" only means anything once the
       bundle has been shown to say it consistently and under a signature that
       verifies.

  Two gates stand in front of all of this and are deliberately not in the list,
  because they are properties of the request rather than of the bundle: the
  request must arrive as `application/json`, and one caller may only publish so
  often. `TechtreeWeb.PublicationController` holds the first and
  `TechtreeWeb.PublicationRate` the second.

  ## What this site does not check, and why

  The participant's own offline verifier walks a longer list, and the
  difference is recorded here rather than implied. This service does **not**
  run:

  * **Linkage.** That the Campaign names the DataPolicy the bundle carries,
    that the TasksetLock holds the tasks the Campaign commits to, that the
    validation receipt validates that lock, that the Campaign commits to that
    receipt, and that the report cites the baseline and candidate experiment
    manifests the bundle carries. Ten edges between eight documents.
  * **The receipt sets.** That each variant's `ordered_receipt_digests` are the
    receipts the bundle carries, in the committed task order, one per task.
  * **The aggregate, recomputed from the episode receipts.** This site
    recomputes the wins, losses and ties from the report's own task rows
    (check 13) and checks those rows against the Campaign's committed task list
    (check 14). It does not go the further step of recomputing the report's
    task rows from the seventy-two signed episode receipts underneath them.
  * **The execution record**, and the `P1` conditions the grade rests on.

  Those are proof-grade bookkeeping, and the reason for leaving them out is
  not that they do not matter. It is that two independent implementations of a
  long list which disagree on one entry reject honest submissions, and the
  canonical encoder alone needed a hundred-file cross-check to get right. The
  participant runs the whole list on their own machine before publishing, and
  anybody can run it again on the bundle the participant still holds. What is
  checked here is checked here; what is not is named here.

  What identifies the entry is the bundle's own `payload_digest`, recomputed
  under check 8. That is a content address for the whole proof — it commits to
  the artifact list, which commits to every file — so the same proof sent twice
  is the same entry however it was wrapped for transport.
  """

  alias Techtree.Canonical
  alias Techtree.Catalog.Digest
  alias Techtree.Catalog.Query
  alias Techtree.Network
  alias Techtree.Network.Error

  @schema_version "techtree.publication-submission.v1alpha1"
  @manifest_path "bundle.json"
  @envelope_keys ~w(payload payload_digest signature)

  @maximum_files 256

  # Member names that would carry an episode, a transcript, a prompt, a reply
  # or a worker log. None of them appears anywhere in the proof format, which
  # is the point: their absence is a property of the format, and a document
  # that has one is not one of ours.
  @forbidden_members ~w(
    completion completions content conversation episode episodes input log logs
    messages output prompt prompts reply replies response responses rollout
    rollouts stderr stdout system_prompt text tool_calls trace traces transcript
    transcripts turns worker_log
  )

  # Where a string stops being a reference and starts being somebody's own
  # machine. A proof bundle records relative paths inside itself and nothing
  # else, so any of these is a leak rather than a reference.
  @local_path_markers [
    "/Users/",
    "/home/",
    "/root/",
    "/private/",
    "/var/",
    "/tmp/",
    "/mnt/",
    "/media/",
    "/opt/",
    "/Volumes/"
  ]

  @home_relative ~r|~[/\\]|
  @windows_drive ~r|[A-Za-z]:[\\/]|
  @unc_prefix "\\\\"

  @checks [
    {:size, "the submission is small enough to be a proof bundle"},
    {:document, "the submission is the four-member document and carries nothing else"},
    {:file_count, "the bundle carries no more files than a proof bundle has"},
    {:file_paths, "every path is one relative path inside the bundle, written once"},
    {:file_bytes, "every file is canonical base64, and none of them is empty"},
    {:manifest, "the bundle carries the signed list of its own files"},
    {:artifacts, "every file hashes to the digest the bundle claims for it"},
    {:payload_digests, "every signed document hashes to the digest written beside it"},
    {:signatures, "every signature verifies under the key the bundle carries"},
    {:key_id, "the fingerprint names the key by hashing it rather than by claiming it"},
    {:report, "the bundle carries the signed result summary it commits to"},
    {:campaign, "the campaign it names is one this site publishes"},
    {:counts, "the wins, losses and ties recompute from the task results"},
    {:membership, "the tasks are the list the campaign committed to, in order"},
    {:data_policy, "the terms the run was carried out under permit publishing this"},
    {:content, "no file in it holds an episode, a transcript, or a path on a machine"},
    {:declarations, "what the submission claims about the bundle is what the bundle says"}
  ]

  defstruct [:raw, :manifest, :report, :campaign, :climb_reference, :data_policy]

  @type t :: %__MODULE__{
          raw: binary(),
          manifest: map(),
          report: map(),
          campaign: map(),
          climb_reference: String.t(),
          data_policy: map()
        }

  @doc """
  The checks this site runs, in the order it runs them, each said in words a
  page can print.
  """
  @spec checks() :: [{atom(), String.t()}]
  def checks, do: @checks

  @doc """
  How many checks a submission has to pass.
  """
  @spec check_count() :: pos_integer()
  def check_count, do: length(@checks)

  @doc """
  The largest number of files one submission may carry.
  """
  @spec maximum_files() :: pos_integer()
  def maximum_files, do: @maximum_files

  @doc """
  Check one submission end to end, or name the first thing wrong with it.
  """
  @spec verify(binary()) :: {:ok, t()} | {:error, Error.t()}
  def verify(raw) when is_binary(raw) do
    with :ok <- within_cap(raw),
         {:ok, document} <- decode_submission(raw),
         :ok <- file_count(document),
         :ok <- file_paths(raw, document),
         {:ok, files} <- decode_files(document),
         {:ok, manifest} <- manifest(files),
         :ok <- artifacts_hash(manifest, files),
         {:ok, envelopes} <- payload_digests(files),
         {:ok, identity} <- executor_identity(manifest),
         :ok <- signatures(envelopes, identity),
         :ok <- key_id(identity),
         {:ok, report} <- report(manifest, envelopes),
         {:ok, campaign, reference} <- campaign(manifest),
         :ok <- counts(report),
         :ok <- membership(report, campaign),
         {:ok, policy} <- data_policy(manifest, files),
         :ok <- content(files),
         :ok <- declarations(document, manifest, report) do
      {:ok,
       %__MODULE__{
         raw: raw,
         manifest: manifest,
         report: report,
         campaign: campaign,
         climb_reference: reference,
         data_policy: policy
       }}
    end
  end

  @doc """
  The digest that addresses this bundle: the manifest's own payload digest.
  """
  @spec digest(t()) :: String.t()
  def digest(%__MODULE__{manifest: manifest}), do: manifest["payload_digest"]

  @doc """
  The participant's signature over the manifest, which is what they signed when
  they said this bundle was theirs.
  """
  @spec participant_signature(t()) :: String.t()
  def participant_signature(%__MODULE__{manifest: manifest}) do
    get_in(manifest, ["signature", "signature"])
  end

  # -- 1. Size --------------------------------------------------------------

  defp within_cap(raw) do
    cap = Network.maximum_body_bytes()

    if byte_size(raw) <= cap do
      :ok
    else
      {:error,
       Error.new(
         :submission_too_large,
         "a published run is a proof bundle, and this is larger than one can be",
         %{"maximum_bytes" => cap, "submitted_bytes" => byte_size(raw)}
       )}
    end
  end

  # -- 2. The submission document -------------------------------------------

  defp decode_submission(raw) do
    case Jason.decode(raw) do
      {:ok,
       %{
         "schema_version" => @schema_version,
         "run_id" => run_id,
         "bundle_digest" => bundle_digest,
         "files" => files
       } = document}
      when is_binary(run_id) and is_binary(bundle_digest) and is_map(files) and
             map_size(document) == 4 ->
        {:ok, document}

      _other ->
        {:error,
         Error.new(
           :submission_malformed,
           "a submission is a #{@schema_version} document with exactly four " <>
             "members: the run it publishes, the digest of the bundle it carries, " <>
             "the files of that bundle, and this version"
         )}
    end
  end

  # -- 3. The file count ----------------------------------------------------

  defp file_count(%{"files" => files}) do
    count = map_size(files)

    if count <= @maximum_files do
      :ok
    else
      {:error,
       Error.new(
         :submission_too_many_files,
         "a proof bundle for a published campaign is under a hundred files, " <>
           "and this carries more than any of them can",
         %{"maximum_files" => @maximum_files, "submitted_files" => count}
       )}
    end
  end

  # -- 4. The paths ---------------------------------------------------------

  # A decoded map cannot show a repeated member, because the second one has
  # already replaced the first by the time it is a map. So the raw bytes are
  # read once more, keeping member order, and the two member lists this site
  # actually depends on are checked for repetition there.
  defp file_paths(raw, %{"files" => files}) do
    with :ok <- written_once(raw) do
      files
      |> Map.keys()
      |> Enum.sort()
      |> Enum.reduce_while(:ok, fn path, :ok ->
        case path_shape(path) do
          :ok -> {:cont, :ok}
          {:error, reason} -> {:halt, {:error, refuse_path(path, reason)}}
        end
      end)
    end
  end

  defp written_once(raw) do
    case Jason.decode(raw, objects: :ordered_objects) do
      {:ok, %Jason.OrderedObject{} = document} ->
        repeated =
          repeated_members(document) ++
            repeated_members(document["files"])

        if repeated == [] do
          :ok
        else
          {:error,
           Error.new(
             :submission_path_invalid,
             "a member of this submission is written twice, and a file that can " <>
               "be written twice is a file that can be changed after it was checked",
             %{"repeated" => Enum.sort(repeated)}
           )}
        end

      _other ->
        :ok
    end
  end

  defp repeated_members(%Jason.OrderedObject{values: values}) do
    names = Enum.map(values, fn {name, _value} -> name end)

    names -- Enum.uniq(names)
  end

  defp repeated_members(_other), do: []

  defp path_shape(path) when is_binary(path) do
    segments = String.split(path, "/")

    cond do
      path == "" -> {:error, "a path is not empty"}
      String.starts_with?(path, "/") -> {:error, "a path inside a bundle is relative"}
      String.contains?(path, "\\") -> {:error, "a path inside a bundle is written with /"}
      Enum.any?(segments, &(&1 in ["", ".", ".."])) -> {:error, "a path names one file directly"}
      true -> :ok
    end
  end

  defp path_shape(_path), do: {:error, "a path is text"}

  defp refuse_path(path, reason) do
    Error.new(
      :submission_path_invalid,
      "a file in this submission is filed under a path a bundle cannot have — " <> reason,
      %{"path" => path}
    )
  end

  # -- 5. The bytes ---------------------------------------------------------

  defp decode_files(%{"files" => files}) do
    files
    |> Enum.sort()
    |> Enum.reduce_while({:ok, %{}}, fn {path, encoded}, {:ok, acc} ->
      case decode_file(encoded) do
        {:ok, bytes} ->
          {:cont, {:ok, Map.put(acc, path, bytes)}}

        {:error, code, sentence} ->
          {:halt, {:error, Error.new(code, sentence, %{"path" => path})}}
      end
    end)
  end

  defp decode_file(encoded) when is_binary(encoded) do
    case Base.decode64(encoded) do
      {:ok, ""} ->
        {:error, :submission_file_empty,
         "a file in this submission has no bytes in it, and an artifact list " <>
           "here describes no such file"}

      {:ok, bytes} ->
        if Base.encode64(bytes) == encoded do
          {:ok, bytes}
        else
          {:error, :submission_file_not_canonical_base64,
           "a file in this submission is base64 written a second way, and the " <>
             "same bytes have exactly one spelling here"}
        end

      :error ->
        {:error, :submission_malformed,
         "every file in a submission is its exact bytes, base64 encoded"}
    end
  end

  defp decode_file(_encoded) do
    {:error, :submission_malformed,
     "every file in a submission is its exact bytes, base64 encoded"}
  end

  # -- 6. The manifest ------------------------------------------------------

  defp manifest(files) do
    with {:ok, bytes} <- Map.fetch(files, @manifest_path),
         {:ok, decoded} <- signed_envelope(bytes) do
      {:ok, decoded}
    else
      _other ->
        {:error,
         Error.new(
           :submission_manifest_missing,
           "a submission carries a signed #{@manifest_path} at its root, and " <>
             "everything this site reads is read out of it",
           %{"path" => @manifest_path}
         )}
    end
  end

  # -- 7. Artifacts ---------------------------------------------------------

  defp artifacts_hash(manifest, files) do
    listed = List.wrap(manifest["payload"]["artifacts"])

    with :ok <- artifact_set(listed, files) do
      Enum.reduce_while(listed, :ok, fn artifact, :ok ->
        bytes = Map.fetch!(files, artifact["relative_path"])

        if Digest.hash_bytes(bytes) == artifact["digest"] and
             byte_size(bytes) == artifact["size"] do
          {:cont, :ok}
        else
          {:halt,
           {:error,
            Error.new(
              :submission_artifact_digest_mismatch,
              "a file in this bundle is not the file the bundle says it is",
              %{
                "path" => artifact["relative_path"],
                "expected_digest" => artifact["digest"],
                "computed_digest" => Digest.hash_bytes(bytes)
              }
            )}}
        end
      end)
    end
  end

  defp artifact_set(listed, files) do
    expected =
      listed |> Enum.map(& &1["relative_path"]) |> MapSet.new() |> MapSet.put(@manifest_path)

    present = files |> Map.keys() |> MapSet.new()

    missing = MapSet.difference(expected, present)
    unlisted = MapSet.difference(present, expected)

    cond do
      not Enum.empty?(missing) ->
        {:error,
         Error.new(
           :submission_artifact_missing,
           "this bundle lists a file it does not carry",
           %{"paths" => Enum.sort(missing)}
         )}

      not Enum.empty?(unlisted) ->
        {:error,
         Error.new(
           :submission_artifact_unlisted,
           "this bundle carries a file it does not list",
           %{"paths" => Enum.sort(unlisted)}
         )}

      true ->
        :ok
    end
  end

  # -- 8. Payload digests ---------------------------------------------------

  defp payload_digests(files) do
    files
    |> Enum.sort()
    |> Enum.reduce_while({:ok, []}, fn {path, bytes}, {:ok, acc} ->
      case signed_envelope(bytes) do
        {:ok, envelope} ->
          case recomputed(envelope) do
            :ok ->
              {:cont, {:ok, [{path, envelope} | acc]}}

            {:error, computed} ->
              {:halt,
               {:error,
                Error.new(
                  :submission_payload_digest_mismatch,
                  "a signed document in this bundle does not hash to the digest it carries",
                  %{
                    "path" => path,
                    "claimed_digest" => envelope["payload_digest"],
                    "computed_digest" => computed
                  }
                )}}
          end

        :plain ->
          {:cont, {:ok, acc}}
      end
    end)
    |> case do
      {:ok, envelopes} -> {:ok, Enum.reverse(envelopes)}
      {:error, error} -> {:error, error}
    end
  end

  defp recomputed(%{"payload" => payload, "payload_digest" => claimed}) do
    case Canonical.encode(payload) do
      {:ok, canonical} ->
        computed = Digest.hash_bytes(canonical)
        if computed == claimed, do: :ok, else: {:error, computed}

      {:error, reason} ->
        {:error, to_string(reason)}
    end
  end

  defp signed_envelope(bytes) do
    with {:ok, decoded} <- Jason.decode(bytes),
         true <- is_map(decoded),
         true <- Enum.sort(Map.keys(decoded)) == Enum.sort(@envelope_keys) do
      {:ok, decoded}
    else
      _other -> :plain
    end
  end

  # -- 9 and 10. The key and what it signed ----------------------------------

  defp executor_identity(manifest) do
    case get_in(manifest, ["payload", "executor_identity"]) do
      %{
        "kind" => "local_ed25519",
        "algorithm" => "ed25519",
        "key_id" => key_id,
        "public_key" => encoded
      }
      when is_binary(key_id) and is_binary(encoded) ->
        case Base.decode64(encoded) do
          {:ok, key} when byte_size(key) == 32 ->
            {:ok, %{kind: :local_ed25519, key_id: key_id, encoded: encoded, key: key}}

          _other ->
            {:error,
             Error.new(
               :submission_malformed,
               "the signing key in this bundle is not 32 bytes of Ed25519 public key"
             )}
        end

      _other ->
        {:error,
         Error.new(
           :submission_malformed,
           "this bundle names no local Ed25519 signing key"
         )}
    end
  end

  defp signatures(envelopes, identity) do
    Enum.reduce_while(envelopes, :ok, fn {path, envelope}, :ok ->
      if signed_by?(envelope, identity) do
        {:cont, :ok}
      else
        {:halt,
         {:error,
          Error.new(
            :submission_signature_invalid,
            "a signature in this bundle does not verify under the key the bundle carries",
            %{"path" => path, "key_id" => identity.key_id}
          )}}
      end
    end)
  end

  defp signed_by?(
         %{"payload_digest" => digest, "signature" => signature},
         %{key_id: key_id, key: key}
       ) do
    with %{"algorithm" => "ed25519", "key_id" => ^key_id, "signature" => encoded} <- signature,
         {:ok, raw} when byte_size(raw) == 64 <- Base.decode64(encoded),
         true <- Digest.valid?(digest) do
      :crypto.verify(:eddsa, :none, digest, raw, [key, :ed25519])
    else
      _other -> false
    end
  end

  defp signed_by?(_envelope, _identity), do: false

  defp key_id(%{key_id: claimed, key: key}) do
    computed = Digest.hash_bytes(key)

    if computed == claimed do
      :ok
    else
      {:error,
       Error.new(
         :submission_key_id_mismatch,
         "the key's fingerprint is not the fingerprint of the key",
         %{"claimed_key_id" => claimed, "computed_key_id" => computed}
       )}
    end
  end

  # -- 11. The report the bundle commits to ----------------------------------

  defp report(manifest, envelopes) do
    root = get_in(manifest, ["payload", "root_report_digest"])

    envelopes
    |> Enum.find(fn {_path, envelope} -> envelope["payload_digest"] == root end)
    |> case do
      {_path, %{"payload" => payload}} when is_map(payload) ->
        {:ok, payload}

      _other ->
        {:error,
         Error.new(
           :submission_report_missing,
           "this bundle names a result summary it does not carry",
           %{"root_report_digest" => root}
         )}
    end
  end

  # -- 12. The campaign this site publishes ----------------------------------

  defp campaign(manifest) do
    digest = get_in(manifest, ["payload", "campaign_spec_digest"])

    case Query.get_climb_by_campaign_digest(to_string(digest)) do
      {:error, _reason} ->
        {:error,
         Error.new(
           :submission_campaign_unpublished,
           "this site publishes no campaign under that fingerprint, " <>
             "and a run can only be published against one it does",
           %{"campaign_spec_digest" => digest}
         )}

      {:ok, climb} ->
        with {:ok, bytes, _entry} <- Query.object_bytes(digest),
             {:ok, campaign} when is_map(campaign) <- Jason.decode(bytes) do
          {:ok, campaign, climb.reference}
        else
          _other ->
            {:error,
             Error.new(
               :submission_campaign_unpublished,
               "this site cannot read the campaign that fingerprint names",
               %{"campaign_spec_digest" => digest}
             )}
        end
    end
  end

  # -- 13. The counts --------------------------------------------------------

  defp counts(report) do
    deltas = report["task_deltas"]
    result = report["primary_result"]

    with true <- is_list(deltas) and deltas != [],
         true <- is_map(result),
         recounted <- recount(deltas),
         true <- recounted == Map.take(result, ["wins", "losses", "ties"]) do
      :ok
    else
      _other ->
        {:error,
         Error.new(
           :submission_counts_inconsistent,
           "the wins, losses and ties in this result do not recompute from its own tasks",
           %{"recomputed" => recount(List.wrap(deltas))}
         )}
    end
  end

  defp recount(deltas) do
    Enum.reduce(deltas, %{"wins" => 0, "losses" => 0, "ties" => 0}, fn delta, acc ->
      Map.update!(acc, outcome(delta["candidate_reward"], delta["baseline_reward"]), &(&1 + 1))
    end)
  end

  defp outcome(candidate, baseline) when is_number(candidate) and is_number(baseline) do
    cond do
      candidate > baseline -> "wins"
      candidate < baseline -> "losses"
      true -> "ties"
    end
  end

  defp outcome(_candidate, _baseline), do: "ties"

  # -- 14. The committed task list -------------------------------------------

  defp membership(report, campaign) do
    committed = get_in(campaign, ["taskset", "membership", "ordered_task_hashes"])
    scored = Enum.map(report["task_deltas"], & &1["task_hash"])

    if is_list(committed) and committed == scored do
      :ok
    else
      {:error,
       Error.new(
         :submission_task_membership_mismatch,
         "the tasks this result scores are not the tasks the campaign committed to",
         %{
           "committed_tasks" => length(List.wrap(committed)),
           "scored_tasks" => length(scored)
         }
       )}
    end
  end

  # -- 15. The terms the run was carried out under ---------------------------

  # The policy is found the way everything else in a bundle is found: by its
  # digest. The manifest names the DataPolicy the run was carried out under,
  # and the file carrying it is whichever one hashes to that — which check 7
  # has already shown is the file the artifact list says it is.
  defp data_policy(manifest, files) do
    named = get_in(manifest, ["payload", "data_policy_digest"])

    with {_path, bytes} <-
           Enum.find(files, fn {_path, bytes} -> Digest.hash_bytes(bytes) == named end),
         {:ok, policy} when is_map(policy) <- Jason.decode(bytes) do
      permits(policy, named)
    else
      _other ->
        {:error,
         Error.new(
           :submission_data_policy_forbids_publication,
           "this bundle names the terms it was carried out under and does not carry them, " <>
             "so there is nothing here that says publishing it is permitted",
           %{"data_policy_digest" => named}
         )}
    end
  end

  defp permits(policy, digest) do
    derived = policy["derived_artifacts"]

    permitted =
      is_map(derived) and derived["uplift_report"] == "public" and
        derived["aggregate_scores"] == "public"

    if permitted do
      {:ok, policy}
    else
      {:error,
       Error.new(
         :submission_data_policy_forbids_publication,
         "the terms this run was carried out under do not make its result and " <>
           "its scores public, and this site publishes neither against them",
         %{
           "data_policy_digest" => digest,
           "uplift_report" => derived_term(derived, "uplift_report"),
           "aggregate_scores" => derived_term(derived, "aggregate_scores")
         }
       )}
    end
  end

  defp derived_term(derived, member) when is_map(derived), do: derived[member]
  defp derived_term(_derived, _member), do: nil

  # -- 16. What is in the files ----------------------------------------------

  # A proof bundle has nowhere to put an episode, a transcript, a prompt, a
  # reply or a worker log: it carries digests, task hashes and scores, and the
  # eleven megabytes of raw episodes stay on the participant's own machine by
  # the same DataPolicy check 15 just read. So this looks for the two shapes
  # that would mean the format had been stretched — a member named for content
  # the format does not carry, and a string that is a path on somebody's own
  # machine rather than a path inside the bundle.
  defp content(files) do
    files
    |> Enum.sort()
    |> Enum.reduce_while(:ok, fn {path, bytes}, :ok ->
      case Jason.decode(bytes) do
        {:ok, document} ->
          case sift(document) do
            :ok -> {:cont, :ok}
            {:error, finding} -> {:halt, {:error, refuse_content(path, finding)}}
          end

        _other ->
          {:halt,
           {:error,
            Error.new(
              :submission_private_content,
              "every file in a proof bundle is a JSON document, and this site " <>
                "cannot read one of these to see what is in it",
              %{"path" => path}
            )}}
      end
    end)
  end

  defp sift(document) when is_map(document) do
    Enum.reduce_while(document, :ok, fn {member, value}, :ok ->
      if member in @forbidden_members do
        {:halt, {:error, {:member, member}}}
      else
        case sift(value) do
          :ok -> {:cont, :ok}
          {:error, finding} -> {:halt, {:error, finding}}
        end
      end
    end)
  end

  defp sift(document) when is_list(document) do
    Enum.reduce_while(document, :ok, fn value, :ok ->
      case sift(value) do
        :ok -> {:cont, :ok}
        {:error, finding} -> {:halt, {:error, finding}}
      end
    end)
  end

  defp sift(value) when is_binary(value) do
    if private_path?(value), do: {:error, {:path, value}}, else: :ok
  end

  defp sift(_value), do: :ok

  defp private_path?(value) do
    String.contains?(value, @local_path_markers) or
      String.contains?(value, @unc_prefix) or
      Regex.match?(@home_relative, value) or
      Regex.match?(@windows_drive, value)
  end

  defp refuse_content(path, {:member, member}) do
    Error.new(
      :submission_private_content,
      "a document in this bundle carries a #{member}, and a proof bundle carries " <>
        "digests and scores rather than the episodes they summarise",
      %{"path" => path, "member" => member}
    )
  end

  defp refuse_content(path, {:path, _value}) do
    Error.new(
      :submission_private_content,
      "a document in this bundle names a location on the machine that produced " <>
        "it, and a bundle records paths inside itself and nothing else",
      %{"path" => path}
    )
  end

  # -- 17. What the submitter said they were sending -------------------------

  defp declarations(document, manifest, report) do
    with :ok <- declared_digest(document["bundle_digest"], manifest["payload_digest"]) do
      declared_run_id(document["run_id"], report["run_id"])
    end
  end

  defp declared_digest(declared, declared), do: :ok

  defp declared_digest(declared, actual) do
    {:error,
     Error.new(
       :submission_bundle_digest_mismatch,
       "this submission declares a bundle digest that is not the digest of " <>
         "the bundle it carries",
       %{"declared_bundle_digest" => declared, "bundle_digest" => actual}
     )}
  end

  defp declared_run_id(declared, declared), do: :ok

  defp declared_run_id(declared, actual) do
    {:error,
     Error.new(
       :submission_run_id_mismatch,
       "this submission declares a run that the signed result inside it does not name",
       %{"declared_run_id" => declared, "run_id" => actual}
     )}
  end
end
