defmodule Techtree.WalletBench.BlankTest do
  # Evidence is public once stored, so a secret that slips through blanking is
  # published. Every known secret and every secret pattern is blanked, also
  # inside JSON strings, while the address and signature the judge checks stay.
  use ExUnit.Case, async: true

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
end
