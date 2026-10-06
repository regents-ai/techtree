defmodule Techtree.Network.Bundle do
  @moduledoc """
  Everything that has to hold before a submission is allowed to become a row.

  A published entry says, in effect, "this site checked this". The only way for
  that sentence to be worth anything is for the checking to happen before the
  row exists, in one place, with no path around it — so this module takes bytes
  and returns either a fully checked bundle or the name of the first check that
  did not hold. `Techtree.Network.Ingest` cannot write without one, and there
  is no other way to get one.

  Twenty checks run, in the order below, and each of them refuses a
  different lie. Nine of them are marked *proof*: the eight the founder
  settled on as the verification depth of this service, with the recount of
  the wins, losses and ties widened into a recomputation of the whole result,
  and the check that the runs differ only in the Skill. The rest are
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
    6. **The manifest.** The bundle carries a signed `bundle.json` at its root,
       in the current proof format, which carries the Skill it measured.
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
       there is nothing to gain by sending anything else. The execution plan
       that published Campaign binds is read beside it, because under v2 it is
       the plan, not the Campaign, that names the harness the run measured.
   13. *Proof.* The report's result recomputes from its own task rows: the
       wins, losses and ties, and the decision, by the rule the published
       Campaign set before either run, over exact sums of the scores.
       `Techtree.Network.Result` says how, and what this site then reads as a
       regression.
   14. *Proof.* The only setting the two runs differ in is a Skill the
       Campaign lets differ, written the way the CLI writes one, and the
       fingerprint it gives the Skill is the one the run with the Skill was set
       up with, so every published result can show the change it measured.

  What checks 13 and 14 work out is stored with the entry as its
  `Techtree.Network.Assessment`, which is what the Result's page reads.
   15. **The Skill.** The bundle carries the Skill it measured: `skill.json`,
       and under `skill/` exactly the files it lists, which give the
       fingerprint the run with the Skill was set up with. Publishing a Result
       makes its Skill public, so the Skill is refused if a path could land
       outside its folder, if it is larger than a Skill may be, or if any file
       in it looks like a private key or an API key. The CLI runs the same list,
       with the same codes, before anything leaves the machine.
   16. *Proof.* Those task rows are the Campaign's committed task list, in the
       same order, exactly — not a subset, not a superset, not a reordering.
   17. **The terms.** The DataPolicy the run cites is carried in the bundle and
       permits exactly this: a public uplift report, public aggregate scores
       and a public Skill. A run carried out under terms that do not permit
       publication is refused rather than published against its owner's own
       stated wishes.
   18. **The content.** No submitted file carries a raw episode, a transcript, a
       prompt, a reply, a worker log, or a path on somebody's own machine. The
       proof format has nowhere to put one, which is exactly why a submission
       carrying one is not a proof bundle and is not stored here. The Skill's
       own files are the one exception: they are the Skill's text, and check 15
       has already read them.
   19. **The rerun.** A report that says it reruns a published Result names one
       this log holds, withdrawn or not, of the same Campaign and the same
       Skill. Nothing more is claimed for it: a rerun is another report from
       someone's own machine, not an independent reproduction.
   20. *Proof.* What the submission claims about the bundle is what the bundle
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
    recomputes the result from the report's own task rows (check 13) and checks
    those rows against the Campaign's committed task list (check 15). It does
    not go the further step of recomputing the report's task rows from the
    seventy-two signed episode receipts underneath them.
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
  alias Techtree.Network.Result

  @schema_version "techtree.publication-submission.v1alpha1"
  @bundle_schema_version "techtree.local-proof-bundle.v1alpha2"
  @manifest_path "bundle.json"
  @skill_path "skill.json"
  @skill_folder "skill/"
  @skill_entry "SKILL.md"
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

  # A Skill is text a person wrote, and it becomes public with its Result. The
  # limits and kinds of file are the CLI's, so a Skill the CLI prepared is one
  # this site accepts.
  @skill_maximum_files 32
  @skill_maximum_file_bytes 131_072
  @skill_maximum_total_bytes 262_144
  @skill_media_types %{
    ".md" => "text/markdown",
    ".txt" => "text/plain",
    ".json" => "application/json",
    ".yaml" => "application/yaml",
    ".yml" => "application/yaml"
  }
  @skill_artifact_keys ~w(files name parent_skill_digest root_digest schema_version source_kind)
  @skill_file_keys ~w(digest media_type path size)

  # What a private key or an API key looks like, the CLI's list exactly. A
  # transaction hash looks exactly like a private key, so a Skill may hold
  # neither. Read as bytes: every pattern is ASCII, so a byte that is not UTF-8
  # matches nothing here, just as the replacement character it decodes to would.
  @secret_patterns [
    {"a private key block", ~r/-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----/},
    {"an API key (sk-)", ~r/(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{20,}/},
    {"a GitHub token (ghp_)", ~r/(?<![A-Za-z0-9_])ghp_[A-Za-z0-9]{36}/},
    {"a GitHub token (github_pat_)", ~r/(?<![A-Za-z0-9_])github_pat_[A-Za-z0-9_]{22,}/},
    {"an AWS access key", ~r/(?<![A-Za-z0-9])AKIA[0-9A-Z]{16}(?![A-Za-z0-9])/},
    {"a Slack token", ~r/(?<![A-Za-z0-9])xox[abprs]-[A-Za-z0-9-]{10,}/},
    {"a 32-byte hex value (a private key or a transaction hash)",
     ~r/(?<![A-Za-z0-9])0x[0-9a-fA-F]{64}(?![A-Za-z0-9])/}
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
    {:manifest, "the bundle carries the signed list of its own files, in the current format"},
    {:artifacts, "every file hashes to the digest the bundle claims for it"},
    {:payload_digests, "every signed document hashes to the digest written beside it"},
    {:signatures, "every signature verifies under the key the bundle carries"},
    {:key_id, "the fingerprint names the key by hashing it rather than by claiming it"},
    {:report, "the bundle carries the signed result summary it commits to"},
    {:campaign, "the report binds a campaign and execution plan this site publishes"},
    {:result,
     "the wins, losses and ties and the decision recompute from the task scores under the " <>
       "rule the campaign set"},
    {:skill_change,
     "the only setting the two runs differ in is the Skill the campaign lets differ, " <>
       "and the run with it was set up with that Skill"},
    {:skill,
     "the bundle carries the Skill it measured, and that Skill holds no secret and is " <>
       "small enough to publish"},
    {:membership, "the tasks are the list the campaign committed to, in order"},
    {:data_policy, "the terms the run was carried out under permit publishing this"},
    {:content, "no file in it holds an episode, a transcript, or a path on a machine"},
    {:rerun, "a rerun names a published Result of the same campaign and the same Skill"},
    {:declarations, "what the submission claims about the bundle is what the bundle says"}
  ]

  defstruct [
    :raw,
    :manifest,
    :report,
    :campaign,
    :execution_plan,
    :campaign_name,
    :skill_digest,
    :climb_reference,
    :data_policy,
    :assessment
  ]

  @type t :: %__MODULE__{
          raw: binary(),
          manifest: map(),
          report: map(),
          campaign: map(),
          execution_plan: map(),
          campaign_name: String.t() | nil,
          skill_digest: String.t(),
          climb_reference: String.t(),
          data_policy: map(),
          assessment: assessment()
        }

  @typedoc """
  What this site worked out about a Result, in the shape of an
  `Techtree.Network.Assessment`.
  """
  @type assessment :: %{
          required(:skill_changes) => [Result.change()],
          optional(atom()) => term()
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
         {:ok, campaign, execution_plan, reference, campaign_name} <- campaign(manifest),
         :ok <- report_context(report, manifest, campaign),
         {:ok, assessment, [%{"digest" => skill_digest} | _skills]} <-
           assessment(report, campaign, files),
         :ok <- skill(files, skill_digest),
         :ok <- membership(report, campaign),
         {:ok, policy} <- data_policy(manifest, files),
         :ok <- content(files),
         {:ok, rerun_of} <- rerun(report, manifest, skill_digest),
         :ok <- declarations(document, manifest, report) do
      {:ok,
       %__MODULE__{
         raw: raw,
         manifest: manifest,
         report: report,
         campaign: campaign,
         execution_plan: execution_plan,
         campaign_name: campaign_name,
         skill_digest: skill_digest,
         climb_reference: reference,
         data_policy: policy,
         assessment: Map.put(assessment, :rerun_of, rerun_of)
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
      |> reduce_while_ok(&checked_path/1)
    end
  end

  defp checked_path(path) do
    case path_shape(path) do
      :ok -> :ok
      {:error, reason} -> {:error, refuse_path(path, reason)}
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
      bundle_version(decoded)
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

  # A bundle made before the proof carried its Skill has nothing for a Result
  # page to show as the change it measured, so only the current format is a
  # proof here.
  defp bundle_version(%{"payload" => %{"schema_version" => @bundle_schema_version}} = manifest),
    do: {:ok, manifest}

  defp bundle_version(manifest) do
    {:error,
     Error.new(
       :submission_bundle_version_unsupported,
       "this site publishes #{@bundle_schema_version} proof bundles, which carry the " <>
         "Skill they measured, and this bundle is not one",
       %{
         "expected" => @bundle_schema_version,
         "found" => get_in(manifest, ["payload", "schema_version"])
       }
     )}
  end

  # -- 7. Artifacts ---------------------------------------------------------

  defp artifacts_hash(manifest, files) do
    listed = List.wrap(manifest["payload"]["artifacts"])

    with :ok <- artifact_set(listed, files) do
      reduce_while_ok(listed, &artifact_matches(&1, files))
    end
  end

  defp artifact_matches(artifact, files) do
    bytes = Map.fetch!(files, artifact["relative_path"])
    computed = Digest.hash_bytes(bytes)

    if computed == artifact["digest"] and byte_size(bytes) == artifact["size"] do
      :ok
    else
      {:error,
       Error.new(
         :submission_artifact_digest_mismatch,
         "a file in this bundle is not the file the bundle says it is",
         %{
           "path" => artifact["relative_path"],
           "expected_digest" => artifact["digest"],
           "computed_digest" => computed
         }
       )}
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
    envelopes =
      for {path, bytes} <- Enum.sort(files),
          {:ok, envelope} <- [signed_envelope(bytes)],
          do: {path, envelope}

    with :ok <- reduce_while_ok(envelopes, &payload_digest_matches/1) do
      {:ok, envelopes}
    end
  end

  defp payload_digest_matches({path, envelope}) do
    case recomputed(envelope) do
      :ok ->
        :ok

      {:error, computed} ->
        {:error,
         Error.new(
           :submission_payload_digest_mismatch,
           "a signed document in this bundle does not hash to the digest it carries",
           %{
             "path" => path,
             "claimed_digest" => envelope["payload_digest"],
             "computed_digest" => computed
           }
         )}
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
        with {:ok, campaign} <- published_object(digest),
             {:ok, execution_plan} <- published_object(campaign["execution_plan_digest"]) do
          {:ok, campaign, execution_plan, climb.reference, campaign_name(climb, digest)}
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

  # A run on the tasks a Climb keeps apart is filed under a name of its own, so
  # the list of Results never shows it as one more run of the Climb's tasks.
  defp campaign_name(climb, digest) do
    if Query.held_out_campaign?(climb, digest),
      do: climb.title <> ", held-out tasks",
      else: climb.title
  end

  defp report_context(report, manifest, campaign) do
    expected = [
      {"schema_version", "techtree.uplift-report.v3"},
      {"campaign_spec_digest", manifest["payload"]["campaign_spec_digest"]},
      {"execution_plan_digest", campaign["execution_plan_digest"]}
    ]

    case Enum.find(expected, fn {field, value} -> Map.get(report, field) != value end) do
      nil ->
        route(report, campaign)

      {field, value} ->
        {:error,
         Error.new(
           :submission_report_context_mismatch,
           "the signed result summary must bind the published campaign and its execution plan",
           %{"field" => field, "expected" => value, "found" => Map.get(report, field)}
         )}
    end
  end

  # A run is one route, one the Campaign offers, and its cost is reported the
  # way that route reports it: Prime reports dollars, the plan does not.
  @route_costs [{"prime_key", "provider_reported"}, {"chatgpt_plan", "plan_included"}]

  defp route(%{"access" => access, "cost_provenance" => provenance}, campaign)
       when {access, provenance} in @route_costs do
    offered = get_in(campaign, ["agents", "subject", "model", "access"])

    if access in offered do
      :ok
    else
      {:error,
       Error.new(
         :submission_report_context_mismatch,
         "the signed result summary names a route its Campaign does not offer",
         %{"field" => "access", "expected" => offered, "found" => access}
       )}
    end
  end

  defp route(report, _campaign) do
    {:error,
     Error.new(
       :submission_report_context_mismatch,
       "the signed result summary must name the route it ran on and how that route " <>
         "reports cost",
       Map.take(report, ["access", "cost_provenance"])
     )}
  end

  # An object this site publishes, read from the exact bytes it serves. The
  # import already refused any catalog whose Campaign binds a plan it does not
  # ship, so a plan that cannot be read here is a served object gone wrong,
  # and the run is refused rather than published against half a definition.
  defp published_object(digest) when is_binary(digest) do
    with {:ok, bytes, _entry} <- Query.object_bytes(digest),
         {:ok, document} when is_map(document) <- Jason.decode(bytes) do
      {:ok, document}
    else
      _other -> :error
    end
  end

  defp published_object(_digest), do: :error

  # -- 13 and 14. The result and the Skill change ----------------------------
  #
  # `Techtree.Network.Result` recomputes both. What this module adds is the
  # candidate run's own Skill list, which the Skill change is checked against.

  defp assessment(report, campaign, files) do
    with {:ok, result} <- Result.assess(report, campaign),
         {:ok, skills} <- candidate_skills(report, campaign, files),
         {:ok, changes} <- Result.skill_change(report, campaign, skills) do
      {:ok, Map.put(result, :skill_changes, changes), skills}
    end
  end

  # The report names the candidate run's settings by the digest of their file,
  # and every file has already passed the signed manifest's digest check, so
  # this reads verified bytes. The Skills sit at the one place in the settings
  # the Campaign lets differ, and a Campaign asks for at least one.
  defp candidate_skills(report, campaign, files) do
    with [allowed] <- get_in(campaign, ["mutation_contract", "allowed_differences"]),
         %{"configuration" => configuration} <-
           candidate_experiment(report["candidate_manifest_digest"], files),
         [_ | _] = skills <- at(configuration, String.split(allowed, "/", trim: true)),
         true <- Enum.all?(skills, &match?(%{"digest" => _digest}, &1)),
         true <- Enum.all?(skills, &Digest.valid?(&1["digest"])) do
      {:ok, skills}
    else
      _other ->
        {:error,
         Error.new(
           :submission_skill_change_invalid,
           "the run with the Skill does not name its Skill by fingerprint in the settings " <>
             "this bundle carries",
           %{"candidate_manifest_digest" => report["candidate_manifest_digest"]}
         )}
    end
  end

  defp at(value, []), do: value
  defp at(%{} = map, [key | path]), do: at(Map.get(map, key), path)
  defp at(_value, _path), do: nil

  defp candidate_experiment(nil, _files), do: nil

  defp candidate_experiment(digest, files) when is_binary(digest) do
    Enum.find_value(files, fn {_path, bytes} ->
      if Digest.hash_bytes(bytes) == digest, do: json_object(bytes)
    end)
  end

  defp candidate_experiment(_digest, _files), do: nil

  defp json_object(bytes) do
    case Jason.decode(bytes) do
      {:ok, document} when is_map(document) -> document
      _other -> nil
    end
  end

  # -- 15. The Skill ----------------------------------------------------------
  #
  # The same list, in the same order and with the same codes, as the CLI runs
  # before anything leaves the machine; the first that fails is the answer.
  # Every file here already hashes to the digest the signed manifest lists for
  # it, so this reads verified bytes.

  defp skill(files, expected_root) do
    sent =
      for {@skill_folder <> path, bytes} <- files, into: %{}, do: {path, bytes}

    with {:ok, artifact} <- skill_artifact(files),
         listed = Enum.map(artifact["files"], & &1["path"]),
         :ok <- skill_paths(listed, sent),
         :ok <- skill_sizes(listed, sent),
         :ok <- skill_fingerprint(artifact, sent, expected_root) do
      skill_secrets(sent)
    end
  end

  defp skill_artifact(files) do
    with {:ok, bytes} <- Map.fetch(files, @skill_path),
         {:ok, artifact} <- Jason.decode(bytes),
         true <- skill_artifact?(artifact) do
      {:ok, artifact}
    else
      _other ->
        {:error,
         Error.new(
           :skill_artifact_invalid,
           "a proof bundle carries its Skill's file list as a techtree.skill.v1alpha1 " <>
             "document at #{@skill_path}, and this bundle does not",
           %{"path" => @skill_path}
         )}
    end
  end

  defp skill_artifact?(
         %{
           "schema_version" => "techtree.skill.v1alpha1",
           "name" => name,
           "root_digest" => root,
           "files" => [_ | _] = entries,
           "source_kind" => "manual",
           "parent_skill_digest" => parent
         } = artifact
       )
       when is_binary(name) and name != "" do
    Enum.sort(Map.keys(artifact)) == @skill_artifact_keys and Digest.valid?(root) and
      (is_nil(parent) or Digest.valid?(parent)) and Enum.all?(entries, &skill_file?/1)
  end

  defp skill_artifact?(_artifact), do: false

  defp skill_file?(
         %{"path" => path, "media_type" => media_type, "size" => size, "digest" => digest} =
           entry
       )
       when is_binary(path) and path != "" and is_binary(media_type) and media_type != "" and
              is_integer(size) and size >= 0 do
    Enum.sort(Map.keys(entry)) == @skill_file_keys and Digest.valid?(digest)
  end

  defp skill_file?(_entry), do: false

  defp skill_paths(listed, sent) do
    with :ok <- reduce_while_ok(listed ++ Enum.sort(Map.keys(sent)), &skill_path/1),
         :ok <- skill_entry(listed) do
      if Enum.sort(Map.keys(sent)) == listed do
        :ok
      else
        {:error,
         Error.new(
           :skill_fingerprint_mismatch,
           "the Skill's files are not exactly the ones its fingerprint lists, in order",
           %{
             "unlisted" => Enum.sort(Map.keys(sent) -- listed),
             "missing" => Enum.sort(listed -- Map.keys(sent))
           }
         )}
      end
    end
  end

  defp skill_path(path) do
    cond do
      path != String.trim(path) or String.starts_with?(path, "/") or
        String.at(path, 1) == ":" or String.contains?(path, "\\") or
          Enum.any?(String.split(path, "/"), &(&1 in ["", ".", ".."])) ->
        {:error,
         Error.new(
           :skill_path_invalid,
           "a Skill path would land outside the Skill's folder",
           %{"path" => path}
         )}

      not Map.has_key?(@skill_media_types, skill_suffix(path)) ->
        {:error,
         Error.new(
           :skill_path_invalid,
           "a Skill holds only .md, .txt, .json, .yaml and .yml files",
           %{"path" => path}
         )}

      true ->
        :ok
    end
  end

  defp skill_entry(listed) do
    if @skill_entry in listed do
      :ok
    else
      {:error,
       Error.new(:skill_path_invalid, "the Skill has no #{@skill_entry}", %{
         "path" => @skill_entry
       })}
    end
  end

  defp skill_suffix(path), do: path |> Path.extname() |> String.downcase()

  defp skill_sizes(listed, sent) do
    oversized =
      Enum.find(Enum.sort(sent), fn {_path, bytes} ->
        byte_size(bytes) > @skill_maximum_file_bytes
      end)

    total = sent |> Map.values() |> Enum.map(&byte_size/1) |> Enum.sum()

    cond do
      length(listed) > @skill_maximum_files ->
        skill_too_large(%{
          "file_count" => length(listed),
          "maximum_files" => @skill_maximum_files
        })

      oversized ->
        skill_too_large(%{
          "path" => elem(oversized, 0),
          "maximum_file_bytes" => @skill_maximum_file_bytes
        })

      total > @skill_maximum_total_bytes ->
        skill_too_large(%{
          "total_bytes" => total,
          "maximum_total_bytes" => @skill_maximum_total_bytes
        })

      true ->
        :ok
    end
  end

  defp skill_too_large(details) do
    {:error,
     Error.new(
       :skill_too_large,
       "a Skill holds at most #{@skill_maximum_files} files, each at most 128 KiB and " <>
         "256 KiB in all, and this one is larger",
       details
     )}
  end

  defp skill_fingerprint(artifact, sent, expected_root) do
    computed = artifact["files"] |> Canonical.encode!() |> Digest.hash_bytes()

    if artifact["root_digest"] == expected_root and computed == expected_root do
      reduce_while_ok(artifact["files"], &skill_file_matches(&1, sent))
    else
      {:error,
       Error.new(
         :skill_fingerprint_mismatch,
         "the Skill's file list does not give the fingerprint the run with the Skill was set up with",
         %{
           "expected" => expected_root,
           "stated" => artifact["root_digest"],
           "computed" => computed
         }
       )}
    end
  end

  defp skill_file_matches(%{"path" => path} = entry, sent) do
    bytes = Map.fetch!(sent, path)

    if byte_size(bytes) == entry["size"] and Digest.hash_bytes(bytes) == entry["digest"] and
         @skill_media_types[skill_suffix(path)] == entry["media_type"] do
      :ok
    else
      {:error,
       Error.new(
         :skill_fingerprint_mismatch,
         "a Skill file is not the file its fingerprint lists",
         %{"path" => path}
       )}
    end
  end

  defp skill_secrets(sent) do
    sent
    |> Enum.sort()
    |> reduce_while_ok(fn {path, bytes} -> skill_secret(path, secret_kind(bytes)) end)
  end

  defp secret_kind(bytes) do
    Enum.find_value(@secret_patterns, fn {kind, pattern} ->
      if Regex.match?(pattern, bytes), do: kind
    end)
  end

  defp skill_secret(_path, nil), do: :ok

  defp skill_secret(path, kind) do
    {:error,
     Error.new(
       :skill_contains_secret,
       "a Skill file contains what looks like #{kind}, and a Skill becomes public " <>
         "with its Result",
       %{"path" => path, "found" => kind}
     )}
  end

  # -- 16. The committed task list -------------------------------------------

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

  # -- 17. The terms the run was carried out under ---------------------------

  # The policy is found the way everything else in a bundle is found: by its
  # digest. The manifest names the DataPolicy the run was carried out under,
  # and the file carrying it is whichever one hashes to that — which check 7
  # has already shown is the file the artifact list says it is.
  # Publishing a Result publishes its Skill, so the terms have to say the Skill
  # is public for a Climb too.
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
    skill_release = get_in(policy, ["candidate_skill", "public_release"])

    permitted =
      is_map(derived) and derived["uplift_report"] == "public" and
        derived["aggregate_scores"] == "public" and skill_release == "required_for_climb"

    if permitted do
      {:ok, policy}
    else
      {:error,
       Error.new(
         :submission_data_policy_forbids_publication,
         "the terms this run was carried out under do not make its result, its " <>
           "scores and its Skill public, and this site publishes none of them against them",
         %{
           "data_policy_digest" => digest,
           "uplift_report" => derived_term(derived, "uplift_report"),
           "aggregate_scores" => derived_term(derived, "aggregate_scores"),
           "candidate_skill" => skill_release
         }
       )}
    end
  end

  defp derived_term(derived, member) when is_map(derived), do: derived[member]
  defp derived_term(_derived, _member), do: nil

  # -- 18. What is in the files ----------------------------------------------

  # A proof bundle has nowhere to put an episode, a transcript, a prompt, a
  # reply or a worker log: it carries digests, task hashes and scores, and the
  # eleven megabytes of raw episodes stay on the participant's own machine by
  # the same DataPolicy check 17 just read. So this looks for the two shapes
  # that would mean the format had been stretched — a member named for content
  # the format does not carry, and a string that is a path on somebody's own
  # machine rather than a path inside the bundle. The Skill's own files are
  # its text rather than documents of the proof format, and check 15 has
  # already read every one of them.
  defp content(files) do
    files
    |> Enum.reject(fn {path, _bytes} -> String.starts_with?(path, @skill_folder) end)
    |> Enum.sort()
    |> reduce_while_ok(fn {path, bytes} -> file_content(path, bytes) end)
  end

  defp file_content(path, bytes) do
    case Jason.decode(bytes) do
      {:ok, document} ->
        content_finding(path, sift(document))

      _other ->
        {:error,
         Error.new(
           :submission_private_content,
           "every file in a proof bundle is a JSON document, and this site " <>
             "cannot read one of these to see what is in it",
           %{"path" => path}
         )}
    end
  end

  defp content_finding(_path, :ok), do: :ok
  defp content_finding(path, {:error, finding}), do: {:error, refuse_content(path, finding)}

  defp sift(document) when is_map(document) do
    reduce_while_ok(document, fn {member, value} ->
      if member in @forbidden_members, do: {:error, {:member, member}}, else: sift(value)
    end)
  end

  defp sift(document) when is_list(document), do: reduce_while_ok(document, &sift/1)

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

  # -- 19. The rerun ----------------------------------------------------------
  #
  # A rerun is the same Campaign and the same Skill, run again and signed by
  # whoever ran it. The original may since have been withdrawn: the rerun
  # still reran it.

  defp rerun(%{"rerun_of" => nil}, _manifest, _skill_digest), do: {:ok, nil}

  defp rerun(%{"rerun_of" => original}, manifest, skill_digest) when is_binary(original) do
    campaign = get_in(manifest, ["payload", "campaign_spec_digest"])

    case Network.Query.get_entry(original) do
      :error ->
        rerun_refused(
          :rerun_original_unknown,
          "this report says it reruns a Result this site has not published",
          original
        )

      {:ok, %{campaign_spec_digest: ^campaign, skill_digest: ^skill_digest}} ->
        {:ok, original}

      {:ok, %{campaign_spec_digest: ^campaign}} ->
        rerun_refused(
          :rerun_skill_mismatch,
          "a rerun measures the same Skill as the Result it reruns, and this one does not",
          original
        )

      {:ok, _entry} ->
        rerun_refused(
          :rerun_campaign_mismatch,
          "a rerun is of the same Campaign as the Result it reruns, and this one is not",
          original
        )
    end
  end

  defp rerun(_report, _manifest, _skill_digest) do
    rerun_refused(
      :rerun_original_unknown,
      "a report names the Result it reruns by its bundle digest, or names none",
      nil
    )
  end

  defp rerun_refused(code, message, original),
    do: {:error, Error.new(code, message, %{"rerun_of" => original})}

  # -- 20. What the submitter said they were sending -------------------------

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

  defp reduce_while_ok(enumerable, check) do
    Enum.reduce_while(enumerable, :ok, fn element, :ok ->
      case check.(element) do
        :ok -> {:cont, :ok}
        {:error, error} -> {:halt, {:error, error}}
      end
    end)
  end
end
