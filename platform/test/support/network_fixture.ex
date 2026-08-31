defmodule Techtree.NetworkFixture do
  @moduledoc """
  A real proof bundle, and ways to damage a copy of it.

  `test/support/fixtures/proof` is one finished run, copied byte for byte off
  the machine that produced it — eighty-four files, every digest and every
  signature as they were written. A check that only ever sees a bundle this
  repository built for the occasion is checking that the repository agrees with
  itself, which is the one thing it was never in doubt about.

  So the honest bundle is read from disk, and every test that wants a refusal
  spoils exactly one thing about a copy of it. Nothing here writes to the
  fixture; the damage is done to the submission document a test is about to
  send.
  """

  alias Techtree.Canonical
  alias Techtree.Catalog.Digest
  alias Techtree.Network.Key

  @root Path.expand("fixtures/proof", __DIR__)
  @schema_version "techtree.publication-submission.v1alpha1"
  @withdrawal_schema_version "techtree.publication-withdrawal.v1alpha1"
  @manifest "bundle.json"

  @doc """
  Every file of the bundle, keyed by its path inside it.
  """
  @spec files() :: %{String.t() => binary()}
  def files do
    @root
    |> Path.join("**/*.json")
    |> Path.wildcard()
    |> Map.new(&{Path.relative_to(&1, @root), File.read!(&1)})
  end

  @doc """
  A submission document carrying these files.

  The two claims the document makes about the bundle are read out of the bundle
  itself, which is what an honest sender does: the run it publishes and the
  digest it is filed under are both in the manifest it is about to send.

  `declared` overrides one of those claims, which is the only way to reach the
  check that a claim has to agree with the bundle it travels with.
  """
  @spec submission(%{String.t() => binary()}, keyword()) :: binary()
  def submission(files \\ files(), declared \\ []) do
    files
    |> Map.new(fn {path, bytes} -> {path, Base.encode64(bytes)} end)
    |> encoded_submission(declared, files)
  end

  @doc """
  A submission document whose files are already encoded, however they were
  encoded.

  This is the only way to reach the checks about the encoding itself, which a
  helper that always encodes correctly could never fail.
  """
  @spec encoded_submission(%{String.t() => term()}, keyword(), %{String.t() => binary()}) ::
          binary()
  def encoded_submission(encoded, declared \\ [], from \\ files()) do
    manifest = from |> Map.get(@manifest, Map.fetch!(files(), @manifest)) |> Jason.decode!()

    Jason.encode!(%{
      "schema_version" => @schema_version,
      "run_id" => Keyword.get(declared, :run_id, manifest["payload"]["run_id"]),
      "bundle_digest" => Keyword.get(declared, :bundle_digest, manifest["payload_digest"]),
      "files" => encoded
    })
  end

  @doc """
  The honest submission, with one file's member written a second time.

  A repeated member cannot be built out of a map, because the second one has
  already replaced the first by the time it is one, so it is spliced into the
  document's own text.
  """
  @spec submission_with_repeated_path(String.t()) :: binary()
  def submission_with_repeated_path(path) do
    String.replace(
      submission(),
      ~s("files":{),
      ~s("files":{"#{path}":"#{Base.encode64("{}")}",),
      global: false
    )
  end

  @doc """
  The digest the honest bundle is filed under: its manifest's payload digest.
  """
  @spec bundle_digest() :: String.t()
  def bundle_digest, do: manifest()["payload_digest"]

  @doc """
  The bundle manifest, decoded.
  """
  @spec manifest() :: map()
  def manifest, do: files() |> Map.fetch!(@manifest) |> Jason.decode!()

  @doc """
  The signed result summary the manifest commits to, decoded.
  """
  @spec report() :: map()
  def report do
    root = manifest()["payload"]["root_report_digest"]

    files()
    |> Enum.map(fn {_path, bytes} -> Jason.decode!(bytes) end)
    |> Enum.find(&(is_map(&1) and &1["payload_digest"] == root))
  end

  @doc """
  The same bundle with one file's bytes replaced.
  """
  @spec replace(String.t(), binary()) :: %{String.t() => binary()}
  def replace(path, bytes), do: Map.put(files(), path, bytes)

  @doc """
  The same bundle with one signed document's payload rewritten.

  The envelope keeps its digest and its signature, so the rewritten document is
  the one a bundle would carry if somebody edited a result after signing it.
  """
  @spec rewrite_payload(String.t(), (map() -> map())) :: %{String.t() => binary()}
  def rewrite_payload(path, transform) do
    envelope = files() |> Map.fetch!(path) |> Jason.decode!()
    rewritten = Map.update!(envelope, "payload", transform)

    replace(path, Canonical.encode!(rewritten))
  end

  @doc """
  The same bundle, made entirely consistent again under a key made here.

  This is what lets a test reach the checks at the far end of the list. A
  bundle whose numbers were edited fails the signature check long before
  anything looks at the numbers, so proving that the count check refuses on its
  own means handing it a bundle that is perfectly signed and simply wrong.
  Every payload digest is recomputed, every envelope is signed again, the
  artifact list is made truthful, the digest the manifest files its data policy
  under is recomputed from the policy the bundle actually carries, and the
  manifest is sealed last.

  The key is generated per call, so nothing here can be confused with the
  participant's key that signed the fixture. Pass `:keys` to sign with a key
  pair of your own, which is what a withdrawal test needs when it has to sign a
  request with the same key the entry carries.

  Pass `:key_id` to have the bundle announce a fingerprint that is not the hash
  of the key it is actually signed with, which is the only way to reach the
  fingerprint check with every signature still verifying. Pass
  `:root_report_digest` to have it commit to a result summary it does not
  carry, and `:data_policy_digest` to have it name terms it does not carry.
  """
  @spec resign(%{String.t() => binary()}, keyword()) :: %{String.t() => binary()}
  def resign(files, options \\ []) do
    {public, private} =
      Keyword.get_lazy(options, :keys, fn -> :crypto.generate_key(:eddsa, :ed25519) end)

    key_id = Keyword.get(options, :key_id, Digest.hash_bytes(public))

    sealed =
      Map.new(files, fn {path, bytes} ->
        {path, if(path == @manifest, do: bytes, else: seal(bytes, key_id, private))}
      end)

    manifest = sealed |> Map.fetch!(@manifest) |> Jason.decode!()

    payload =
      manifest["payload"]
      |> Map.put("artifacts", listed(manifest["payload"]["artifacts"], sealed))
      |> Map.put(
        "root_report_digest",
        Keyword.get_lazy(options, :root_report_digest, fn ->
          root_report_digest(sealed, manifest)
        end)
      )
      |> Map.put(
        "data_policy_digest",
        Keyword.get_lazy(options, :data_policy_digest, fn ->
          data_policy_digest(manifest, sealed)
        end)
      )
      |> put_in(["executor_identity", "key_id"], key_id)
      |> put_in(["executor_identity", "public_key"], Base.encode64(public))

    Map.put(
      sealed,
      @manifest,
      Canonical.encode!(%{
        "payload" => payload,
        "payload_digest" => Digest.hash_bytes(Canonical.encode!(payload)),
        "signature" => signature(Digest.hash_bytes(Canonical.encode!(payload)), key_id, private)
      })
    )
  end

  @doc """
  A signed withdrawal request for one bundle, made with one participant key.
  """
  @spec withdrawal(String.t(), {binary(), binary()}, keyword()) :: binary()
  def withdrawal(bundle_digest, {public, private}, options \\ []) do
    payload =
      Keyword.get(options, :payload, %{
        "schema_version" => @withdrawal_schema_version,
        "bundle_digest" => bundle_digest,
        "requested_at" => DateTime.to_iso8601(DateTime.utc_now())
      })

    key_id = Keyword.get(options, :key_id, Digest.hash_bytes(public))
    digest = Keyword.get(options, :payload_digest, Digest.hash_bytes(Canonical.encode!(payload)))

    Canonical.encode!(%{
      "payload" => payload,
      "payload_digest" => digest,
      "signature" => signature(digest, key_id, private)
    })
  end

  @doc """
  A key pair, for a test that has to sign as the publisher and then sign again
  as the same person withdrawing.
  """
  @spec key_pair() :: {binary(), binary()}
  def key_pair, do: :crypto.generate_key(:eddsa, :ed25519)

  @doc """
  Publish one submission through the ingest, with the network key this build
  holds and the origin this build answers at — the same two things the
  controller hands it, so a receipt made here is the receipt a caller would get.
  """
  @spec publish(binary(), keyword()) :: term()
  def publish(submitted \\ submission(), options \\ []) do
    {:ok, key} = Key.load()

    Techtree.Network.Ingest.accept(
      submitted,
      key,
      Keyword.put_new(options, :origin, TechtreeWeb.Endpoint.url())
    )
  end

  @doc """
  One entry written straight through the create action the ingest uses.

  This exists for exactly one test: the branch that refuses a submission whose
  digest is already held under a different set of bytes. Every honest
  submission carrying one bundle is the same four members over the same files,
  so that state cannot be reached by sending anything — it can only be
  arranged, and arranging it is what proves the branch answers.
  """
  @spec seed_entry(keyword()) :: struct()
  def seed_entry(overrides \\ []) do
    manifest = manifest()
    payload = manifest["payload"]

    attributes =
      %{
        id: Ash.UUID.generate(),
        log_sequence: 1,
        accepted_at: DateTime.utc_now(),
        bundle_digest: manifest["payload_digest"],
        submission_bytes: submission(),
        submission_digest: Digest.hash_bytes(submission()),
        run_id: payload["run_id"],
        campaign_spec_digest: payload["campaign_spec_digest"],
        data_policy_digest: payload["data_policy_digest"],
        climb_reference: "hello-world-climb@1",
        participant_kind: :local_ed25519,
        participant_key_id: payload["executor_identity"]["key_id"],
        participant_public_key: payload["executor_identity"]["public_key"],
        subject_provider: "prime",
        subject_model: "qwen/qwen3.7-flash",
        subject_harness: "hermes-agent",
        subject_harness_version: "0.19.0",
        baseline_mean: 0.0,
        candidate_mean: 1.0,
        absolute_delta: 1.0,
        wins: 1,
        losses: 0,
        ties: 0,
        task_count: 1,
        statuses: %{},
        decision: "accepted",
        proof_grade: "P1",
        verification_checks_run: 1,
        verification_checks_passed: 1,
        task_deltas: [],
        receipt_bytes: "{}",
        receipt_digest: Digest.hash_bytes("{}"),
        network_key_id: Digest.hash_bytes("key")
      }
      |> Map.merge(Map.new(overrides))

    Techtree.Network.record_publication_entry!(attributes, authorize?: false)
  end

  defp seal(bytes, key_id, private) do
    envelope = Jason.decode!(bytes)

    if is_map(envelope) and
         Enum.sort(Map.keys(envelope)) == ["payload", "payload_digest", "signature"] do
      digest = Digest.hash_bytes(Canonical.encode!(envelope["payload"]))

      Canonical.encode!(%{
        "payload" => envelope["payload"],
        "payload_digest" => digest,
        "signature" => signature(digest, key_id, private)
      })
    else
      bytes
    end
  end

  defp signature(digest, key_id, private) do
    %{
      "algorithm" => "ed25519",
      "key_id" => key_id,
      "signature" => Base.encode64(:crypto.sign(:eddsa, :none, digest, [private, :ed25519]))
    }
  end

  defp listed(artifacts, files) do
    Enum.map(artifacts, fn artifact ->
      bytes = Map.fetch!(files, artifact["relative_path"])

      artifact
      |> Map.put("digest", Digest.hash_bytes(bytes))
      |> Map.put("size", byte_size(bytes))
    end)
  end

  defp root_report_digest(files, manifest) do
    report_path =
      Enum.find_value(manifest["payload"]["artifacts"], fn artifact ->
        path = artifact["relative_path"]
        envelope = files |> Map.fetch!(path) |> Jason.decode!()

        if is_map(envelope) and is_map(envelope["payload"]) and
             envelope["payload"]["schema_version"] == "techtree.uplift-report.v1alpha1",
           do: path
      end)

    files |> Map.fetch!(report_path) |> Jason.decode!() |> Map.fetch!("payload_digest")
  end

  # Which file is the data policy is decided by the artifact list the manifest
  # arrived with, and its digest is then taken again from whatever that file
  # now holds. A test that edits the policy therefore gets a bundle that names
  # the policy it carries, which is the only way to reach the check about what
  # the policy says rather than the one about it being absent.
  defp data_policy_digest(manifest, files) do
    named = manifest["payload"]["data_policy_digest"]

    path =
      Enum.find_value(manifest["payload"]["artifacts"], fn artifact ->
        if artifact["digest"] == named, do: artifact["relative_path"]
      end)

    case path && Map.get(files, path) do
      nil -> named
      bytes -> Digest.hash_bytes(bytes)
    end
  end
end
