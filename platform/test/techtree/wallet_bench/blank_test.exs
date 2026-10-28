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
    -----BEGIN PGP PRIVATE KEY BLOCK-----
    lQOYBGcPgpPrivateKeyBodyLine
    -----END PGP PRIVATE KEY BLOCK-----
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
          "PrivateKeyBody",
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

  # An agent may retype a phrase in its own layout (security assessment of
  # 19 Oct, finding 5).
  test "a recovery phrase retyped in capitals or joined by other marks is blanked" do
    words = String.split(@phrase)

    for written <- [
          Enum.map_join(words, " ", &String.capitalize/1),
          String.upcase(@phrase),
          Enum.join(words, "-"),
          Enum.join(words, " | "),
          Enum.join(words, "/"),
          Enum.join(words, "_"),
          Enum.join(words, "."),
          Enum.join(words, "; "),
          Enum.join(words, "+"),
          Enum.join(words, "\u00A0")
        ] do
      assert Blank.blank("phrase: #{written} done", []) ==
               "phrase: [redacted: recovery phrase] done",
             written
    end

    numbered =
      words |> Enum.with_index(1) |> Enum.map_join(" ", fn {word, n} -> "#{n}-#{word}" end)

    assert Blank.blank("phrase: #{numbered} done", []) ==
             "phrase: 1-[redacted: recovery phrase] done"
  end

  # Tool results are often JSON written inside JSON, so a line break between
  # two words reaches the record as `\\n`, or as `\r\n` from Windows.
  test "a recovery phrase in a JSON string, escaped once or twice, is blanked" do
    words = String.split(@phrase)

    for joiner <- ["\n", "\r\n"], depth <- [1, 2] do
      inner = Enum.join(words, joiner)
      text = if depth == 1, do: inner, else: Jason.encode!(inner)
      blanked = Blank.blank(Jason.encode!(%{"t" => text}), [])

      assert blanked =~ "[redacted: recovery phrase]", inspect({joiner, depth})
      refute blanked =~ "winner", inspect({joiner, depth})
    end
  end

  # `n`, `r` and `t` are letters an email address or a base58 key may start
  # with; the escape's letter stays, so the JSON stays readable.
  test "a secret right after an escaped line break leaves the JSON whole" do
    solana = String.duplicate("4vJ9JU1bJJE96FWSJKvHsmmFADCg4gpZQff4P3bkLKi", 2)

    for {secret, mark} <- [
          {"someone@example.com", "[redacted: email address]"},
          {solana, "[redacted: 64-byte base58 value: a Solana private key or signature]"}
        ],
        joiner <- ["\n", "\r\n", "\t"],
        depth <- [1, 2] do
      inner = "line" <> joiner <> secret
      text = if depth == 1, do: inner, else: Jason.encode!(inner)

      assert {:ok, %{"o" => blanked}} =
               Jason.decode(Blank.blank(Jason.encode!(%{"o" => text}), []))

      blanked = if depth == 1, do: blanked, else: Jason.decode!(blanked)
      assert blanked == "line" <> joiner <> mark
    end
  end

  # An agent driving a tool through a terminal records its colour codes, and a
  # progress line ends in a carriage return or backspaces; a secret printed
  # right after one is blanked, in plain text and in JSON once or twice, the
  # code itself stays and the JSON stays whole (review of 27 Oct).
  @shapes [
    {"0x" <> String.duplicate("1f", 32), "32-byte hex value: a private key or a hash"},
    {"0X" <> String.duplicate("A9", 32), "32-byte hex value: a private key or a hash"},
    {String.duplicate("e3", 32), "32-byte hex value: a private key or a hash"},
    {"sk-ant-api03-" <> String.duplicate("Q", 40), "API key"},
    {"bk_ABCDEFGHJKLMNPQRSTUV", "API key"},
    {"ows_key_Zx9Qm2Lk8Vt4Rb7Nc1Yw6Hd3", "wallet agent token"},
    {"someone@example.com", "email address"},
    {String.duplicate("4vJ9JU1bJJE96FWSJKvHsmmFADCg4gpZQff4P3bkLKi", 2),
     "64-byte base58 value: a Solana private key or signature"},
    {@phrase, "recovery phrase"}
  ]

  @codes [
    "\e[32m",
    "\e[1;32m",
    "\e[38:5:208m",
    "\e[?25h",
    "\e[2K\e[1G",
    "\e(B\e[m",
    "\\x1b[32m",
    "\\033[1m",
    "\\e[0;33m",
    "\r",
    "\b\b\b",
    "\f",
    "\a",
    "\t"
  ]

  # Two levels deep, `\\b`, `\\f` and `\\u` are read both as an escape and as a
  # written backslash before a letter, so a blank there may take the escape's
  # letter: the secret is gone and the outer JSON stays whole.
  test "a secret right after a colour code or a returned line is blanked, and the code stays" do
    for {secret, label} <- @shapes, code <- @codes, depth <- [0, 1, 2] do
      text =
        Enum.reduce(1..depth//1, "out: " <> code <> secret, fn _depth, text ->
          Jason.encode!(text)
        end)

      blanked = Blank.blank(text, [])
      mark = "[redacted: " <> label <> "]"

      assert blanked =~ mark
      refute blanked =~ String.slice(secret, -12, 12)
      if depth > 0, do: assert({:ok, _outer} = Jason.decode(blanked))

      case unwrap(blanked, depth) do
        {:ok, read} -> assert read == "out: " <> code <> mark, inspect({secret, code, depth})
        {:error, _inner} -> assert depth == 2 and code =~ ~r/[\a\b\f]/, inspect({secret, code})
      end
    end
  end

  defp unwrap(text, 0), do: {:ok, text}

  defp unwrap(text, depth) do
    with {:ok, inner} <- Jason.decode(text), do: unwrap(inner, depth - 1)
  end

  test "an address right after a colour code stays, also written with 0X" do
    for address <- [@address, "0X" <> String.slice(@address, 2..-1//1)],
        code <- @codes,
        depth <- [0, 1, 2] do
      written = "to " <> code <> address <> "\e[0m"
      text = Enum.reduce(1..depth//1, written, fn _depth, text -> Jason.encode!(text) end)

      assert Blank.blank(text, []) == text
    end
  end

  test "a recovery phrase with a colour code around each word is blanked" do
    shown =
      @phrase
      |> String.split()
      |> Enum.with_index(1)
      |> Enum.map_join("  ", fn {word, n} -> "#{n}. \e[1m#{word}\e[0m" end)

    for text <- [shown, Jason.encode!(shown)] do
      blanked = Blank.blank(text, [])
      assert blanked =~ "[redacted: recovery phrase]"
      refute blanked =~ "sausage"
    end
  end

  # A written backslash, escaped in JSON, may come right before a key that
  # starts with `b` or `f` or an address that starts with `u`.
  test "a secret right after a written backslash is blanked" do
    for {secret, label} <- [
          {"b" <> String.duplicate("1f", 31) <> "1",
           "32-byte hex value: a private key or a hash"},
          {"bk_ABCDEFGHJKLMNPQRSTUV", "API key"},
          {"user@corp.example", "email address"}
        ],
        depth <- [1, 2] do
      text = Enum.reduce(1..depth, "CORP\\" <> secret, fn _depth, text -> Jason.encode!(text) end)

      read =
        Enum.reduce(1..depth, Blank.blank(text, []), fn _depth, text -> Jason.decode!(text) end)

      assert read == "CORP\\[redacted: " <> label <> "]"
    end
  end

  # A run of backslashes, as JSON written many levels deep makes, is read once
  # from its start, and so is each colour code.
  @tag timeout: 10_000
  test "a megabyte of backslashes or colour codes before a key is blanked in moments" do
    key = "0x" <> String.duplicate("1f", 32)

    for filler <- [String.duplicate("\\", 1_000_000), String.duplicate("\e[0m", 250_000)] do
      assert String.ends_with?(
               Blank.blank(filler <> "\e[32m" <> key, []),
               "\e[32m[redacted: 32-byte hex value: a private key or a hash]"
             )
    end
  end

  # A long run of an address's characters is read once, not once for each of
  # its characters: a large output is blanked in moments.
  @tag timeout: 10_000
  test "a megabyte of letters before an email address is blanked in moments" do
    text = String.duplicate("ab-", 350_000) <> " someone@example.com"
    assert String.ends_with?(Blank.blank(text, []), " [redacted: email address]")
  end

  # A picture a harness read is written into its output as base64; a screenshot
  # of a recovery phrase would otherwise be published inside the transcript
  # (reviews of 20 Oct, after pictures stopped being recorded as files).
  @starts [
    <<0x89, "PNG\r\n", 0x1A, "\n">>,
    <<0xFF, 0xD8, 0xFF, 0xE0>>,
    "GIF89a",
    "RIFF" <> <<0, 0, 0, 0>> <> "WEBP",
    "BM" <> <<1234::little-32, 0::32>>,
    "BM" <> <<0xFFFFFF::little-32, 0::32>>,
    "II*" <> <<0>>,
    "MM" <> <<0, 42>>,
    "II+" <> <<0, 8, 0>>,
    <<0, 0, 0, 0x1C>> <> "ftypavif",
    <<0, 0, 0, 0x18>> <> "ftypheic",
    <<0, 0, 0, 0x1F>> <> "ftypmif1",
    <<0, 0, 0, 0x20>> <> "ftypavis",
    <<0, 0, 0, 0x18>> <> "ftypheim",
    <<0, 0, 0, 0x18>> <> "ftyphevc",
    <<0, 0, 0, 0x18>> <> "ftypmsf1",
    "<!DOCTYPE svg PUBLIC",
    "<svg xmlns=\"http://www.w3.org/2000/svg\">",
    "<?xml version=\"1.0\"?>",
    "%PDF-1.7\n"
  ]

  defp refute_any_of(blanked, picture) do
    for piece <- picture |> String.codepoints() |> Enum.chunk_every(16, 16, :discard) do
      refute blanked =~ Enum.join(piece), "part of the picture survived blanking"
    end
  end

  # Some writers use the web-safe alphabet, `-` and `_` for `+` and `/`, and
  # drop the padding; some indent every line after the first.
  property "a picture written into a transcript is blanked whole, however it is written" do
    check all(
            start <- member_of(@starts),
            rest <- binary(min_length: 80, max_length: 600),
            before <- member_of(["", "screenshot:\n", "1\t"]),
            wrap <- member_of([nil, "\n", "\r\n"]),
            indent <- member_of(["", "    ", "\t"]),
            escape <- member_of([:none, :json, :html_safe]),
            encode <- member_of([&Base.encode64/1, &Base.url_encode64(&1, padding: false)])
          ) do
      picture = encode.(start <> rest)

      written =
        if wrap,
          do:
            picture
            |> String.codepoints()
            |> Enum.chunk_every(76)
            |> Enum.map_join(wrap <> indent, &Enum.join/1),
          else: picture

      text =
        case escape do
          :none ->
            before <> written <> "\nkept as written"

          escape ->
            Jason.encode!(%{"data" => before <> written, "note" => "kept"}, escape: escape)
        end

      blanked = Blank.blank(text, [])

      assert blanked =~ "[redacted: picture]"
      assert blanked =~ if(escape == :none, do: "\nkept as written", else: "kept")
      refute_any_of(blanked, String.replace(picture, "/", ""))
      if escape != :none, do: assert({:ok, _} = Jason.decode(blanked))
    end
  end

  # A mostly white picture is mostly `/`, each escaped as `\\/` by some writers:
  # one step of the match per escape, past the default limit at this size.
  for {name, bytes} <- [mixed: <<1, 2, 3>>, white: <<255, 255, 255>>],
      escape <- [:json, :html_safe] do
    test "a #{name} picture of several megabytes is blanked whole (#{escape})" do
      picture = Base.encode64(hd(@starts) <> :binary.copy(unquote(bytes), 1_400_000))

      assert Blank.blank(Jason.encode!(%{"data" => picture}, escape: unquote(escape)), []) ==
               ~s({"data":"[redacted: picture]"})
    end
  end

  # Inside JSON the line break is the escape `\n`, which a picture's own lines may use too.
  test "the line after a padded picture stays" do
    picture = Base.encode64(hd(@starts) <> :binary.copy(<<7>>, 101))
    assert String.ends_with?(picture, "=")

    assert Blank.blank(~s({"out": "#{picture}\\n#{@address} sent"}), []) ==
             ~s({"out": "[redacted: picture]\\n#{@address} sent"})
  end

  # The line after an unpadded picture can start with letters a picture uses;
  # a key there is blanked whole, not cut short by the picture's match.
  test "a key on the line after an unpadded picture is blanked whole" do
    picture = Base.encode64(hd(@starts) <> :binary.copy(<<9>>, 103))
    refute String.ends_with?(picture, "=")
    key = "sk-ant-api03-" <> String.duplicate("Q", 40)

    blanked = Blank.blank(~s({"out": "#{picture}\\n#{key}"}), Blank.known(key, []))

    assert blanked == ~s({"out": "[redacted: picture]\\n[redacted: API key]"})
  end

  # An address, key or hash alone on the line after an unpadded picture is base64
  # too, but keeps its own rule: the judge checks the address and needs the kind.
  test "a 0x value on the line after an unpadded picture keeps its own rule" do
    picture = Base.encode64(hd(@starts) <> :binary.copy(<<9>>, 103))
    refute String.ends_with?(picture, "=")
    key = "0x" <> String.duplicate("1f", 32)
    hex = "[redacted: 32-byte hex value: a private key or a hash]"

    for indent <- ["", "  "] do
      assert Blank.blank("#{picture}\n#{indent}#{@address}\n#{indent}#{key}\n", []) ==
               "[redacted: picture]\n#{indent}#{@address}\n#{indent}#{hex}\n"

      assert Blank.blank(Jason.encode!(%{"o" => "#{picture}\n#{indent}#{@address}"}), []) ==
               Jason.encode!(%{"o" => "[redacted: picture]\n#{indent}#{@address}"})
    end
  end

  # A known secret can start with letters a picture uses and hold a quote; it
  # is blanked whole before the picture rule reads the line it starts.
  test "a password with a quote on the line after an unpadded picture is blanked whole" do
    picture = Base.encode64(hd(@starts) <> :binary.copy(<<9>>, 103))
    password = ~s(Xk9mP2"vL#q8$wR)
    known = Blank.known(nil, [%{"path" => "/home/a/.wallet/password", "values" => [password]}])
    marker = "[redacted: password, from /home/a/.wallet/password]"

    assert Blank.blank("$ base64 shot.png\n#{picture}\n#{password}\n$ ", known) ==
             "$ base64 shot.png\n[redacted: picture]\n#{marker}\n$ "

    assert Blank.blank(Jason.encode!(%{"o" => picture <> "\n" <> password <> "\n"}), known) ==
             Jason.encode!(%{"o" => "[redacted: picture]\n" <> marker <> "\n"})
  end
end
