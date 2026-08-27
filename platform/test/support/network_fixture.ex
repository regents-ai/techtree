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

  @root Path.expand("fixtures/proof", __DIR__)
  @schema_version "techtree.submission.v1alpha1"
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
  """
  @spec submission(%{String.t() => binary()}) :: binary()
  def submission(files \\ files()) do
    Jason.encode!(%{
      "schema_version" => @schema_version,
      "files" => Map.new(files, fn {path, bytes} -> {path, Base.encode64(bytes)} end)
    })
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
  artifact list is made truthful, and the manifest is sealed last.

  The key is generated per call, so nothing here can be confused with the
  participant's key that signed the fixture.

  Pass `:key_id` to have the bundle announce a fingerprint that is not the hash
  of the key it is actually signed with, which is the only way to reach the
  fingerprint check with every signature still verifying.
  """
  @spec resign(%{String.t() => binary()}, keyword()) :: %{String.t() => binary()}
  def resign(files, options \\ []) do
    {public, private} = :crypto.generate_key(:eddsa, :ed25519)
    key_id = Keyword.get(options, :key_id, Digest.hash_bytes(public))

    sealed =
      Map.new(files, fn {path, bytes} ->
        {path, if(path == @manifest, do: bytes, else: seal(bytes, key_id, private))}
      end)

    manifest = sealed |> Map.fetch!(@manifest) |> Jason.decode!()

    payload =
      manifest["payload"]
      |> Map.put("artifacts", listed(manifest["payload"]["artifacts"], sealed))
      |> Map.put("root_report_digest", root_report_digest(sealed, manifest))
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
end
