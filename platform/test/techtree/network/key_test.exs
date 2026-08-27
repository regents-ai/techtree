defmodule Techtree.Network.KeyTest do
  @moduledoc """
  The key this site countersigns with, and the two things that matter about it
  besides signing: that it is only ever the configured one, and that its private
  half cannot get out.

  There is no key in this repository, so every test here makes its own and puts
  it in the application environment for the length of the test. That is also
  what `test/test_helper.exs` does once for the suite, and it is the whole of
  how a key ever reaches this code.
  """

  use ExUnit.Case, async: false

  alias Techtree.Catalog.Digest
  alias Techtree.Network.Key

  setup do
    configured = Application.get_env(:techtree, Key)
    on_exit(fn -> Application.put_env(:techtree, Key, configured) end)
    :ok
  end

  describe "loading" do
    test "derives the public half and the fingerprint from the configured private half" do
      {public, private} = configure()

      assert {:ok, key} = Key.load()

      assert key.public == public
      assert key.private == private
      assert key.key_id == Digest.hash_bytes(public)
    end

    test "the published reference is the key, written the way this protocol writes one" do
      {public, _private} = configure()

      {:ok, key} = Key.load()

      assert Key.reference(key) == %{
               "algorithm" => "ed25519",
               "key_id" => Digest.hash_bytes(public),
               "public_key" => Base.encode64(public)
             }
    end

    test "a build with nothing configured holds no key" do
      Application.delete_env(:techtree, Key)

      assert Key.load() == :error
    end

    test "a configured value that is not 32 bytes of key is not a key" do
      for unusable <- [
            "",
            "not base64 !!",
            Base.encode64(:crypto.strong_rand_bytes(31)),
            Base.encode64(:crypto.strong_rand_bytes(64))
          ] do
        Application.put_env(:techtree, Key, private_key: unusable)

        assert Key.load() == :error
      end
    end
  end

  describe "the private half" do
    test "is not in what the module hands out" do
      {_public, private} = configure()

      {:ok, key} = Key.load()

      refute Key.reference(key) |> Map.values() |> Enum.any?(&(&1 =~ Base.encode64(private)))

      signature = Key.countersign(key, Digest.hash_bytes("anything"))

      refute signature["signature"] == Base.encode64(private)
    end

    test "is not in what the struct prints" do
      # `inspect/1` is how a key would reach a log without anybody meaning it
      # to: a crash report, a debugging call, a supervisor's state dump. The
      # struct prints its fingerprint and nothing else.
      {public, private} = configure()

      {:ok, key} = Key.load()

      printed = inspect(key)

      assert printed == ~s(#Techtree.Network.Key<key_id: "#{key.key_id}", ...>)
      refute printed =~ inspect(private)
      refute printed =~ inspect(public)
      refute printed =~ Base.encode64(private)
    end
  end

  describe "countersigning" do
    test "signs the digest string itself, so a verifier needs only the digest and the key" do
      {public, _private} = configure()

      {:ok, key} = Key.load()
      digest = Digest.hash_bytes("a payload somebody canonicalized")

      signature = Key.countersign(key, digest)

      assert signature["algorithm"] == "ed25519"
      assert signature["key_id"] == key.key_id

      assert :crypto.verify(
               :eddsa,
               :none,
               digest,
               Base.decode64!(signature["signature"]),
               [public, :ed25519]
             )

      refute :crypto.verify(
               :eddsa,
               :none,
               Digest.hash_bytes("a different payload"),
               Base.decode64!(signature["signature"]),
               [public, :ed25519]
             )
    end
  end

  defp configure do
    {public, private} = :crypto.generate_key(:eddsa, :ed25519)
    Application.put_env(:techtree, Key, private_key: Base.encode64(private))

    {public, private}
  end
end
