defmodule Techtree.WalletBench.BlankTest do
  # Evidence is public once stored, so a secret that slips through blanking is
  # published. Every known secret and every secret pattern is blanked, also
  # inside JSON strings, while the address and signature the judge checks stay.
  use ExUnit.Case, async: true
  use ExUnitProperties

  alias Techtree.WalletBench.Blank

  @address "0xf6ca0D12952504075664BD5fa3ea98511f482eEa"
  @signature "0x" <> String.duplicate("ab", 65)
  @phrase "legal winner thank year wave sausage worth useful legal winner thank yellow"

  test "known secrets, patterns and recovery phrases are blanked; addresses and signatures stay" do
    known =
      Blank.known("model-key-value-123", [
        %{"path" => "/home/bench/.foundry/recovery/w.password", "values" => [~s(pa"ss\\word-123)]}
      ])

    text = """
    password: pa"ss\\word-123
    {"output": "pa\\"ss\\\\word-123"}
    key 0x#{String.duplicate("1f", 32)}
    bare {"k": "\\n#{String.duplicate("2e", 32)}"}
    agent {"k": "\\nows_key_Zx9Qm2Lk8Vt4Rb7Nc1Yw6Hd3"}
    solana #{String.duplicate("4vJ9JU1bJJE96FWSJKvHsmmFADCg4gpZQff4P3bkLKi", 2)}
    keypair [#{Enum.join(1..64, ",")}]
    -----BEGIN EC PRIVATE KEY-----
    MHcCAQEEIBkg4LVWM9nuwNSk3yByxZpYRTBnVJk5oLh1mUQ+gL9zoAoGCCqGSM49
    -----END EC PRIVATE KEY-----
    bankr bk_ABCDEFGHJKLMNPQRSTUV and model model-key-value-123
    list ["#{String.replace(@phrase, " ", ~s(", "))}"]
    openai sk-proj-abcdefghijklmnopqrstuvwxyz
    open https://wallet.example/login?code=482913 now
    mail someone@example.com
    seed: #{@phrase}
    {"text": "#{String.replace(@phrase, " ", "\\n")}"}
    address #{@address} signature #{@signature}
    """

    blanked = Blank.blank(text, known)

    for secret <- [
          "pa\"ss",
          "pa\\\"ss",
          String.duplicate("1f", 32),
          String.duplicate("2e", 32),
          "ows_key_Zx9",
          "4vJ9JU1b",
          "1,2,3",
          "MHcCAQEE",
          "bk_ABC",
          "model-key-value",
          "sk-proj",
          "482913",
          "someone@",
          "sausage"
        ] do
      refute blanked =~ secret, "#{secret} survived blanking"
    end

    assert blanked =~ "[redacted: password, from /home/bench/.foundry/recovery/w.password]"
    assert blanked =~ "[redacted: recovery phrase]"
    assert blanked =~ "address #{@address} signature #{@signature}"
  end

  # A picture a harness read is written into its output as base64; a screenshot
  # of a recovery phrase would otherwise be published inside the transcript
  # (reviews of 20 Oct, after pictures stopped being recorded as files).
  @starts [
    <<0x89, "PNG\r\n", 0x1A, "\n">>,
    <<0xFF, 0xD8, 0xFF, 0xE0>>,
    "GIF89a",
    "RIFF" <> <<0, 0, 0, 0>> <> "WEBP"
  ]

  defp refute_any_of(blanked, picture) do
    for piece <- picture |> String.codepoints() |> Enum.chunk_every(16, 16, :discard) do
      refute blanked =~ Enum.join(piece), "part of the picture survived blanking"
    end
  end

  property "a picture written into a transcript is blanked whole, however it is written" do
    check all(
            start <- member_of(@starts),
            rest <- binary(min_length: 80, max_length: 600),
            before <- member_of(["", "screenshot:\n", "1\t"]),
            wrap <- member_of([nil, "\n", "\r\n"]),
            escape <- member_of([:none, :json, :html_safe])
          ) do
      picture = Base.encode64(start <> rest)

      written =
        if wrap,
          do:
            picture
            |> String.codepoints()
            |> Enum.chunk_every(76)
            |> Enum.map_join(wrap, &Enum.join/1),
          else: picture

      text =
        case escape do
          :none ->
            before <> written <> " kept"

          escape ->
            Jason.encode!(%{"data" => before <> written, "note" => "kept"}, escape: escape)
        end

      blanked = Blank.blank(text, [])

      assert blanked =~ "[redacted: picture]"
      assert blanked =~ "kept"
      refute_any_of(blanked, String.replace(picture, "/", ""))
      if escape != :none, do: assert({:ok, _} = Jason.decode(blanked))
    end
  end

  test "a picture of several megabytes is blanked whole" do
    picture = Base.encode64(hd(@starts) <> :binary.copy(<<1, 2, 3>>, 2_200_000))
    blanked = Blank.blank(~s({"data": "#{picture}"}), [])

    assert blanked == ~s({"data": "[redacted: picture]"})
  end

  # Inside JSON the line break is the escape `\n`, which a picture's own lines may use too.
  test "the line after a padded picture stays" do
    picture = Base.encode64(hd(@starts) <> :binary.copy(<<7>>, 101))
    assert String.ends_with?(picture, "=")

    assert Blank.blank(~s({"out": "#{picture}\\n#{@address} sent"}), []) ==
             ~s({"out": "[redacted: picture]\\n#{@address} sent"})
  end
end
