defmodule Techtree.WalletBench.SiteSecretsTest do
  # Failure text is stored and shown, so the site's own keys are blanked from it
  # even when they have no vendor prefix a pattern would know.
  use ExUnit.Case, async: false

  alias Techtree.WalletBench.{Blank, Machine}

  setup do
    bankr = Application.get_env(:techtree, :wallet_bench_bankr_api_key)
    sprites = Application.get_env(:regent_sprites, :token)
    bench = Application.get_env(:techtree, Techtree.WalletBench, [])

    Application.put_env(:techtree, :wallet_bench_bankr_api_key, "plainbankrvalue42")
    Application.put_env(:regent_sprites, :token, "plainspritesvalue42")

    Application.put_env(
      :techtree,
      Techtree.WalletBench,
      Keyword.put(bench, :model_key, "plainmodelvalue42")
    )

    on_exit(fn ->
      Application.put_env(:techtree, :wallet_bench_bankr_api_key, bankr)
      Application.put_env(:regent_sprites, :token, sprites)
      Application.put_env(:techtree, Techtree.WalletBench, bench)
    end)
  end

  test "stored failure text never keeps the site's own keys" do
    text =
      Machine.describe_error(
        "failed with plainmodelvalue42, plainbankrvalue42 and plainspritesvalue42"
      )

    refute text =~ "plainmodelvalue42"
    refute text =~ "plainbankrvalue42"
    refute text =~ "plainspritesvalue42"
  end

  test "a key that straddles a log tail's cut leaves none of itself behind" do
    # The cut falls inside the key: 10 bytes of it before the last 20, 7 after.
    log = String.duplicate("a", 100) <> "plainmodelvalue42" <> String.duplicate("b", 13)

    tail = Blank.last(log, Blank.site_known(), 20)

    refute tail =~ "value42"
    refute tail =~ "lue42"
  end

  test "a fragment at the start of a full log window is not kept when blanking shrinks the rest" do
    # The window starts inside a secret: its last 40 characters, then a long
    # known value that blanking shrinks well below its 2,120 bytes.
    fragment = String.duplicate("f", 40)
    long_known = String.duplicate("k", 2_120)
    filler = String.duplicate("z", 4_000 - 40 - 2_120)
    window = fragment <> long_known <> filler

    tail = Blank.last_of_window(window, [{long_known, "keystore"}], 2_000, 2_000)

    refute tail =~ fragment
  end
end
