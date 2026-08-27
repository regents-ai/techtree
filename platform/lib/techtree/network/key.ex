defmodule Techtree.Network.Key do
  @moduledoc """
  The key this site countersigns with, and the only place its private half is
  read.

  Decision 0038 made publishing symmetric. The participant signs their run; the
  network signs that it accepted it. That symmetry is what lets an accepted
  entry be checked later by somebody who trusts neither party's word about the
  other, and it is only worth anything if the network's key behaves like a key
  rather than like a setting. Three rules make it one, and they are enforced
  here and nowhere else.

  *The private half is operational configuration.* It is read from
  `config :techtree, Techtree.Network.Key, private_key: ...`, which
  `config/runtime.exs` fills from the `TECHTREE_NETWORK_SIGNING_KEY`
  environment variable: the base64 of the 32 bytes of an Ed25519 private key.
  There is no default and no key anywhere in this repository — not in a
  configuration file, not in a fixture, not as an example. A production release
  refuses to boot without one, in the same place and for the same reason
  `SECRET_KEY_BASE` and `PHX_HOST` do.

  *It is never printed.* The struct redacts it from `inspect/1`, so it cannot
  reach a log through a crash report or a debugging call. The two ways this
  module can fail — nothing configured, or a value that is not 32 bytes of key
  — are the same bare `:error` with no detail, because a refusal that described
  the value would be a refusal that leaked part of it.

  *The public half is published.* `GET /api/v1/network-key` serves it as the
  three-member document every public key in this protocol is written as, so
  anybody holding a receipt can fetch the key it names and check the signature
  without asking this site for anything else. `TechtreeWeb.NetworkKeyController`
  is that address and `Techtree.Network.Receipt` is what signs with the key.

  **A build with no key configured does not publish.** The publish address
  answers `503` and appends nothing, and the key address answers `503` too.
  That is the whole of the behaviour, and it was chosen over the two
  alternatives on purpose. Generating a key when none is found would sign
  receipts that verify against a key nobody can look up and that changes on the
  next boot — worse than not signing, because it looks like it worked.
  Accepting the run and returning an unsigned receipt would hand back a
  document the participant's own CLI refuses, after the entry was already on
  the log. Refusing before anything is written leaves the participant able to
  publish the identical bundle later, unchanged, and get a real receipt for it.
  """

  alias Techtree.Catalog.Digest

  @derive {Inspect, only: [:key_id]}
  defstruct [:key_id, :public, :private]

  @typedoc """
  A loaded key: its fingerprint, its public half, and its private half.
  """
  @type t :: %__MODULE__{key_id: String.t(), public: binary(), private: binary()}

  @doc """
  The configured key, or `:error` when this build holds none it can use.
  """
  @spec load() :: {:ok, t()} | :error
  def load do
    with encoded when is_binary(encoded) <- configured(),
         {:ok, private} when byte_size(private) == 32 <- Base.decode64(encoded),
         {public, ^private} <- :crypto.generate_key(:eddsa, :ed25519, private) do
      {:ok, %__MODULE__{key_id: Digest.hash_bytes(public), public: public, private: private}}
    else
      _other -> :error
    end
  end

  @doc """
  The public half, written the way every public key in this protocol is.

  The fingerprint is derived rather than configured: it is the hash of the
  public bytes, the same rule the ingest holds a participant's key to.
  """
  @spec reference(t()) :: %{String.t() => String.t()}
  def reference(%__MODULE__{key_id: key_id, public: public}) do
    %{"algorithm" => "ed25519", "key_id" => key_id, "public_key" => Base.encode64(public)}
  end

  @doc """
  Sign one digest string, the way every signature in this protocol is made.

  What is signed is the digest itself rather than the bytes it summarises, so a
  verifier needs the digest and the public key and nothing else.
  """
  @spec countersign(t(), String.t()) :: %{String.t() => String.t()}
  def countersign(%__MODULE__{key_id: key_id, private: private}, digest)
      when is_binary(digest) do
    %{
      "algorithm" => "ed25519",
      "key_id" => key_id,
      "signature" => Base.encode64(:crypto.sign(:eddsa, :none, digest, [private, :ed25519]))
    }
  end

  defp configured do
    :techtree |> Application.get_env(__MODULE__, []) |> Keyword.get(:private_key)
  end
end
