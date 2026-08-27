defmodule Techtree.Network.Bundle do
  @moduledoc """
  Everything that has to hold before a submission is allowed to become a row.

  A published entry says, in effect, "this site checked this". The only way for
  that sentence to be worth anything is for the checking to happen before the
  row exists, in one place, with no path around it — so this module takes bytes
  and returns either a fully checked bundle or the name of the first check that
  did not hold. `Techtree.Network.Ingest` cannot write without one, and there
  is no other way to get one.

  Eight things are checked, and each of them refuses a different lie.

    1. The body is under a hard cap. A proof bundle has no transcripts in it and
       is a few hundred kilobytes; anything much larger is not one.
    2. Every file hashes to the digest the bundle's own artifact list claims for
       it, and the bundle carries exactly the files that list names — no fewer,
       so nothing is missing, and no more, so nothing rode along unaccounted
       for.
    3. Every signed envelope's `payload_digest` is the digest of its payload's
       canonical form, recomputed here. A digest written beside the thing it
       describes proves nothing on its own.
    4. Every signature verifies as Ed25519 over that digest, under the public
       key the bundle carries. What is signed is the digest string itself, so a
       verifier needs only the digest and the key.
    5. The key's fingerprint is the hash of the key. It is derived, not
       asserted, so a bundle cannot claim somebody else's identifier.
    6. The Campaign the run names is one this site publishes. This is the check
       that makes spam uninteresting: a submission has to be a run of a
       comparison we defined, against tasks we committed to in advance, and
       there is nothing to gain by sending anything else.
    7. The report's wins, losses and ties recompute from its own task rows.
    8. Those task rows are the Campaign's committed task list, in the same
       order, exactly — not a subset, not a superset, not a reordering.

  Two things follow from the fifth and sixth together that are worth saying
  outright. The site is checking that a receipt is internally consistent and
  signed by the key it names. It is not checking that the run happened, because
  it cannot: it did not watch it, and nothing in the bundle could make it able
  to. Every entry on the log says so.

  What identifies the entry is the bundle's own `payload_digest`, recomputed
  under check three. That is a content address for the whole proof — it commits
  to the artifact list, which commits to every file — so the same proof sent
  twice is the same entry however it was wrapped for transport.

  One more rule is here for a reason that is not about proof at all. The
  submitted document may carry the proof and nothing else, because those bytes
  are stored and served back at a public address, and a document that allowed
  anything beside the proof would be a way to have this site host whatever
  somebody wanted to put in it.
  """

  alias Techtree.Canonical
  alias Techtree.Catalog.Digest
  alias Techtree.Catalog.Query
  alias Techtree.Network
  alias Techtree.Network.Error

  @schema_version "techtree.submission.v1alpha1"
  @manifest_path "bundle.json"
  @envelope_keys ~w(payload payload_digest signature)

  @checks [
    {:size, "the submission is small enough to be a proof bundle"},
    {:artifacts, "every file hashes to the digest the bundle claims for it"},
    {:payload_digests, "every signed document hashes to the digest written beside it"},
    {:signatures, "every signature verifies under the key the bundle carries"},
    {:key_id, "the fingerprint names the key by hashing it rather than by claiming it"},
    {:campaign, "the campaign it names is one this site publishes"},
    {:counts, "the wins, losses and ties recompute from the task results"},
    {:membership, "the tasks are the list the campaign committed to, in order"}
  ]

  defstruct [:raw, :manifest, :report, :campaign, :climb_reference]

  @type t :: %__MODULE__{
          raw: binary(),
          manifest: map(),
          report: map(),
          campaign: map(),
          climb_reference: String.t()
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
  Check one submission end to end, or name the first thing wrong with it.
  """
  @spec verify(binary()) :: {:ok, t()} | {:error, Error.t()}
  def verify(raw) when is_binary(raw) do
    with :ok <- within_cap(raw),
         {:ok, document} <- decode_submission(raw),
         {:ok, files} <- decode_files(document),
         {:ok, manifest} <- envelope(files, @manifest_path),
         :ok <- artifacts_hash(manifest, files),
         {:ok, envelopes} <- payload_digests(files),
         {:ok, identity} <- executor_identity(manifest),
         :ok <- signatures(envelopes, identity),
         :ok <- key_id(identity),
         {:ok, report} <- report(manifest, envelopes),
         {:ok, campaign, reference} <- campaign(manifest),
         :ok <- counts(report),
         :ok <- membership(report, campaign) do
      {:ok,
       %__MODULE__{
         raw: raw,
         manifest: manifest,
         report: report,
         campaign: campaign,
         climb_reference: reference
       }}
    end
  end

  @doc """
  The digest that addresses this bundle: the manifest's own payload digest.
  """
  @spec digest(t()) :: String.t()
  def digest(%__MODULE__{manifest: manifest}), do: manifest["payload_digest"]

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

  # -- The submission document ----------------------------------------------

  # The document carries the proof and nothing else. Anything a submitter added
  # beside it would be bytes this site stored and served back at a public
  # address, which is the one way arbitrary text could reach a surface here, so
  # a document with anything else in it is not a submission.
  defp decode_submission(raw) do
    case Jason.decode(raw) do
      {:ok, %{"schema_version" => @schema_version, "files" => files} = document}
      when is_map(files) and map_size(document) == 2 ->
        {:ok, document}

      _other ->
        {:error,
         Error.new(
           :submission_malformed,
           "a submission is a #{@schema_version} document whose only contents " <>
             "are the files of one proof bundle"
         )}
    end
  end

  defp decode_files(%{"files" => files}) do
    Enum.reduce_while(files, {:ok, %{}}, fn {path, encoded}, {:ok, acc} ->
      case decode_file(encoded) do
        {:ok, bytes} ->
          {:cont, {:ok, Map.put(acc, path, bytes)}}

        :error ->
          {:halt,
           {:error,
            Error.new(
              :submission_malformed,
              "every file in a submission is its exact bytes, base64 encoded",
              %{"path" => path}
            )}}
      end
    end)
  end

  defp decode_file(encoded) when is_binary(encoded), do: Base.decode64(encoded)
  defp decode_file(_encoded), do: :error

  # -- 2. Artifacts ---------------------------------------------------------

  defp artifacts_hash(manifest, files) do
    listed = manifest["payload"]["artifacts"]

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

  # -- 3. Payload digests ---------------------------------------------------

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

  defp envelope(files, path) do
    with {:ok, bytes} <- Map.fetch(files, path),
         {:ok, decoded} <- signed_envelope(bytes) do
      {:ok, decoded}
    else
      _other ->
        {:error,
         Error.new(
           :submission_malformed,
           "a submission carries a signed #{path} at its root",
           %{"path" => path}
         )}
    end
  end

  # -- 4 and 5. The key and what it signed -----------------------------------

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

  # -- The report the bundle commits to --------------------------------------

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
           :submission_malformed,
           "this bundle names a result summary it does not carry",
           %{"root_report_digest" => root}
         )}
    end
  end

  # -- 6. The campaign this site publishes -----------------------------------

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

  # -- 7. The counts ---------------------------------------------------------

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

  # -- 8. The committed task list --------------------------------------------

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
end
