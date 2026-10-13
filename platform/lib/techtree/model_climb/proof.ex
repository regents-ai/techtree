defmodule Techtree.ModelClimb.Proof do
  @moduledoc """
  The eight checks a Model Climb proof has to hold before this site keeps it
  (contract `docs/spec/model-climb-v1.md`, section 3.5), in the contract's order.

  A proof is one JSON document: a signed manifest and the contract objects it
  lists. Every digest is recomputed here from the RFC 8785 form of what it
  names, so nothing the sender wrote beside a value is taken on trust. The
  full graph check stays with `regents techtree proof verify`; this module
  answers only what the contract says the site checks.

  A refusal names the first check that did not hold, in a sentence safe to
  show the sender.
  """

  alias Techtree.Canonical
  alias Techtree.Catalog.Digest

  @proof_version "techtree.model-climb.proof.v1alpha1"
  @object_version "techtree.model-climb.v1alpha1"
  @maximum_bytes 1_048_576
  @maximum_objects 64

  @kinds ~w(ModelStudySpec DatasetRelease BenchmarkRelease TrainingRecipe ResolvedModelPlan
            ModelArtifact TrainingAttempt ModelUpliftReport ServiceComparisonReport DeploymentRelease)

  @results %{
    "execution" => ~w(succeeded failed cancelled indeterminate),
    "integrity" => ~w(verified invalid incomplete),
    "comparison" => ~w(valid invalid exploratory),
    "outcome" => ~w(uplift tie regression inconclusive),
    "release_gate" => ~w(pass fail insufficient_evidence not_evaluated),
    "attestation" => ~w(participant identified_executor independently_reproduced)
  }

  @cells ~w(both_correct base_only_correct candidate_only_correct neither_correct)

  @typedoc "A checked proof: what the site records about it."
  @type t :: %{
          report_digest: String.t(),
          signer_key_id: String.t(),
          request_digest: String.t(),
          results: map(),
          paired_outcomes: map(),
          proof: binary()
        }

  @typedoc "The first check that did not hold, and why."
  @type refusal :: {:error, %{check: String.t(), message: String.t()}}

  @doc "The largest proof document, in bytes, this site reads."
  def maximum_bytes, do: @maximum_bytes

  @doc "Check a decoded proof document."
  @spec verify(map()) :: {:ok, t()} | refusal()
  def verify(document) do
    with {:ok, canonical} <- document_shape(document),
         {:ok, objects} <- objects(document["objects"]),
         {:ok, payload} <- manifest(document["manifest"]),
         :ok <- signature(document["manifest"]),
         :ok <- carried(payload, objects),
         {:ok, report} <- report(payload, objects),
         :ok <- references(report, objects),
         :ok <- attestation(report) do
      {:ok,
       %{
         report_digest: report["digest"],
         signer_key_id: payload["signer"]["key_id"],
         request_digest: Digest.hash_bytes(canonical),
         results: report["spec"]["results"],
         paired_outcomes: report["spec"]["paired_outcomes"],
         proof: canonical
       }}
    end
  end

  # 1. Size and shape of the document.
  defp document_shape(document) do
    with {:ok, canonical} <- canonical(document, "document") do
      cond do
        byte_size(canonical) > @maximum_bytes ->
          refuse("document", "the proof is larger than #{@maximum_bytes} bytes")

        not exact_keys?(document, ~w(schema_version manifest objects)) ->
          refuse("document", "a proof has exactly schema_version, manifest and objects")

        document["schema_version"] != @proof_version ->
          refuse("document", "this site reads proofs of version #{@proof_version}")

        not is_list(document["objects"]) or length(document["objects"]) > @maximum_objects ->
          refuse("document", "objects is a list of at most #{@maximum_objects} objects")

        true ->
          {:ok, canonical}
      end
    end
  end

  # 2. Every object recomputes to its digest, once each.
  defp objects(list) do
    list
    |> Enum.reduce_while({:ok, %{}}, fn object, {:ok, seen} ->
      case object(object) do
        {:ok, digest} when is_map_key(seen, digest) ->
          {:halt, refuse("objects", "#{digest} appears twice")}

        {:ok, digest} ->
          {:cont, {:ok, Map.put(seen, digest, object)}}

        refusal ->
          {:halt, refusal}
      end
    end)
  end

  defp object(object) do
    cond do
      not exact_keys?(object, ~w(schema_version kind spec operational digest)) ->
        refuse(
          "objects",
          "every object has exactly schema_version, kind, spec, operational and digest"
        )

      object["schema_version"] != @object_version ->
        refuse("objects", "every object is of version #{@object_version}")

      object["kind"] not in @kinds ->
        refuse("objects", "#{inspect(object["kind"])} is not a Model Climb kind")

      true ->
        object_digest(object)
    end
  end

  defp object_digest(%{"digest" => claimed} = object) do
    case digest(Map.take(object, ~w(schema_version kind spec)), "objects") do
      {:ok, ^claimed} ->
        {:ok, claimed}

      {:ok, _other} ->
        refuse("objects", "#{inspect(claimed)} is not the digest of its object")

      refusal ->
        refusal
    end
  end

  # 3. The manifest's shape and its payload digest.
  defp manifest(manifest) do
    payload = is_map(manifest) && manifest["payload"]

    cond do
      not exact_keys?(manifest, ~w(payload payload_digest signature)) ->
        refuse("manifest", "the manifest has exactly payload, payload_digest and signature")

      not exact_keys?(payload, ~w(schema_version report objects signer)) ->
        refuse(
          "manifest",
          "the manifest's payload has exactly schema_version, report, objects and signer"
        )

      payload["schema_version"] != @proof_version ->
        refuse("manifest", "the manifest is of version #{@proof_version}")

      not sorted_digests?(payload["objects"]) ->
        refuse("manifest", "the manifest lists every object's digest once, sorted")

      not signer?(payload["signer"]) ->
        refuse("manifest", "the signer is a local Ed25519 key")

      true ->
        payload_digest(manifest)
    end
  end

  defp payload_digest(%{"payload" => payload, "payload_digest" => claimed}) do
    case digest(payload, "manifest") do
      {:ok, ^claimed} -> {:ok, payload}
      {:ok, _other} -> refuse("manifest", "payload_digest is not the digest of the payload")
      refusal -> refusal
    end
  end

  # 4. The key's fingerprint and the signature.
  defp signature(%{"payload" => %{"signer" => signer}} = manifest) do
    key = Base.decode64!(signer["public_key"])

    with :ok <- key_id(signer, key), do: signed(manifest, signer["key_id"], key)
  end

  defp signed(
         %{
           "payload_digest" => digest,
           "signature" => %{"algorithm" => "ed25519", "key_id" => key_id, "signature" => encoded}
         },
         key_id,
         key
       )
       when is_binary(encoded) do
    with {:ok, raw} when byte_size(raw) == 64 <- Base.decode64(encoded),
         true <- :crypto.verify(:eddsa, :none, digest, raw, [key, :ed25519]) do
      :ok
    else
      _other -> refuse("signature", "the signature does not verify under the signer's key")
    end
  end

  defp signed(_manifest, _key_id, _key),
    do:
      refuse(
        "signature",
        "the signature is {algorithm: ed25519, key_id, signature} by the signer"
      )

  defp key_id(%{"key_id" => claimed}, key) do
    if Digest.hash_bytes(key) == claimed,
      do: :ok,
      else: refuse("signature", "the signer's key_id is not the digest of its public key")
  end

  # 5. The objects carried are exactly the ones listed.
  defp carried(%{"objects" => listed}, objects) do
    if Enum.sort(Map.keys(objects)) == listed,
      do: :ok,
      else: refuse("objects", "the objects carried are not exactly the ones the manifest lists")
  end

  # 6. The report the manifest names.
  defp report(%{"report" => digest}, objects) do
    case Map.fetch(objects, digest) do
      {:ok, %{"kind" => "ModelUpliftReport", "spec" => spec} = report} ->
        with :ok <- report_spec(spec), do: {:ok, report}

      _other ->
        refuse("report", "report names no ModelUpliftReport the proof carries")
    end
  end

  defp report_spec(spec) do
    cond do
      not exact_keys?(
        spec,
        ~w(artifact benchmark_release evaluator_outputs paired_outcomes uncertainty results limitations)
      ) ->
        refuse("report", "the report's spec has exactly the fields section 3.2 names")

      not evaluator_outputs?(spec["evaluator_outputs"]) ->
        refuse("report", "evaluator_outputs is at least one digest")

      not paired_outcomes?(spec["paired_outcomes"]) ->
        refuse("report", "the paired outcomes do not add up")

      not uncertainty?(spec["uncertainty"]) ->
        refuse(
          "report",
          "the uncertainty interval is out of order or its confidence is not between 0 and 1"
        )

      not results?(spec["results"]) ->
        refuse("report", "the result fields take only the values section 3.3 lists")

      not limitations?(spec["limitations"]) ->
        refuse("report", "limitations is a list of sentences")

      true ->
        :ok
    end
  end

  defp evaluator_outputs?([_ | _] = digests), do: Enum.all?(digests, &Digest.valid?/1)
  defp evaluator_outputs?(_other), do: false

  defp limitations?(sentences) when is_list(sentences), do: Enum.all?(sentences, &non_empty?/1)
  defp limitations?(_other), do: false

  defp paired_outcomes?(outcomes) do
    counts = ["cases", "positives", "negatives" | @cells]

    exact_keys?(outcomes, counts) and
      Enum.all?(counts, &(is_integer(outcomes[&1]) and outcomes[&1] >= 0)) and
      Enum.sum(Enum.map(@cells, &outcomes[&1])) == outcomes["cases"] and
      outcomes["positives"] + outcomes["negatives"] == outcomes["cases"]
  end

  defp uncertainty?(uncertainty) do
    exact_keys?(uncertainty, ~w(method confidence interval_low interval_high)) and
      non_empty?(uncertainty["method"]) and
      Enum.all?(~w(confidence interval_low interval_high), &is_number(uncertainty[&1])) and
      uncertainty["confidence"] > 0 and uncertainty["confidence"] < 1 and
      uncertainty["interval_low"] <= uncertainty["interval_high"]
  end

  defp results?(results) do
    exact_keys?(results, Map.keys(@results)) and
      Enum.all?(@results, fn {field, values} -> results[field] in values end)
  end

  # 7. The two objects the report names.
  defp references(%{"spec" => spec}, objects) do
    if kind(objects, spec["artifact"]) == "ModelArtifact" and
         kind(objects, spec["benchmark_release"]) == "BenchmarkRelease",
       do: :ok,
       else:
         refuse(
           "references",
           "the proof carries the report's artifact as a ModelArtifact and its benchmark_release as a BenchmarkRelease"
         )
  end

  defp kind(objects, digest), do: get_in(objects, [digest, "kind"])

  # 8. An upload is the participant's own claim.
  defp attestation(%{"spec" => %{"results" => %{"attestation" => "participant"}}}), do: :ok

  defp attestation(_report),
    do:
      refuse(
        "attestation",
        "an uploaded report's attestation is participant; Techtree gives the other levels itself"
      )

  # -- Helpers ------------------------------------------------------------

  defp canonical(value, check) do
    case Canonical.encode(value) do
      {:ok, bytes} ->
        {:ok, bytes}

      {:error, _reason} ->
        refuse(check, "the document holds a value JSON cannot write canonically")
    end
  end

  defp digest(value, check) do
    with {:ok, bytes} <- canonical(value, check), do: {:ok, Digest.hash_bytes(bytes)}
  end

  defp exact_keys?(map, keys) when is_map(map), do: Enum.sort(Map.keys(map)) == Enum.sort(keys)
  defp exact_keys?(_other, _keys), do: false

  defp sorted_digests?(list) when is_list(list) and list != [],
    do: Enum.all?(list, &Digest.valid?/1) and list == Enum.uniq(Enum.sort(list))

  defp sorted_digests?(_other), do: false

  defp signer?(%{"kind" => "local_ed25519", "algorithm" => "ed25519"} = signer) do
    exact_keys?(signer, ~w(kind algorithm key_id public_key)) and Digest.valid?(signer["key_id"]) and
      match?({:ok, <<_::binary-size(32)>>}, Base.decode64(signer["public_key"] || ""))
  end

  defp signer?(_other), do: false

  defp non_empty?(value), do: is_binary(value) and String.trim(value) != ""

  defp refuse(check, message), do: {:error, %{check: check, message: message}}
end
