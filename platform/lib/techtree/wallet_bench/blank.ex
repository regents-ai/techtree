defmodule Techtree.WalletBench.Blank do
  @moduledoc """
  Blanks secrets out of a turn's evidence before anything is stored.

  First every known secret: each value read from the tested account's
  secret-looking files (`machine/secrets.py`), the model key and supplied
  operator keys regardless of what the agent left on disk. Each is
  blanked as written and as it appears inside a JSON string, and the blank
  names the file it came from. Then every picture written out as base64 text
  (PNG, JPEG, GIF, WebP, BMP, TIFF, AVIF, HEIC or SVG, as a harness shows one
  it read, and PDF, which can carry one), since a screenshot can hold a secret
  no other rule sees. Then patterns: PEM and PGP private keys, sign-in links
  that carry a code, email addresses, API keys with a vendor's prefix (Anthropic,
  OpenAI, Bankr, Zerion, Privy, Circle), the Open Wallet Standard's agent token
  (Zerion's signing token), 32-byte hex values with or without `0x` (a
  private key looks like a transaction hash, so the blank says it may be
  either), 64-byte base58 values (a Solana key looks like a Solana signature)
  and Solana keys written as 64 numbers, and runs of 12 or more
  recovery-phrase words, also as a quoted list. Every blank says what kind of
  thing it hid, so the judge can still rule on a secret that was shown. EVM
  addresses and signatures are longer or shorter than these shapes and stay.

  A value at the start of an output line inside a JSON string follows the
  escape `\\n` or `\\t`, so the prefixed and fixed-length rules also open after
  one; a plain word boundary would miss it there.
  """

  @words_path Application.app_dir(:techtree, "priv/wallet_bench/bip39-english.txt")
  @external_resource @words_path
  @words @words_path |> File.read!() |> String.split() |> MapSet.new()

  @phrase_length 12

  @patterns [
    {~r/-----BEGIN [A-Z ]*PRIVATE KEY[A-Z ]*-----.*?-----END [A-Z ]*PRIVATE KEY[A-Z ]*-----/s,
     "private key"},
    {~r{https?://[^\s"'<>\\]*[?&#](?:code|token|otp|magic|auth)[^\s"'<>\\]*}i, "sign-in link"},
    # An address starts where its characters do, or after an escape, never on
    # the escape's letter; read possessively, each start is tried once.
    {~r/(?:(?<=\\[nrt])|(?<![A-Za-z0-9._%+\-\\])|(?<=\\)(?![nrt]))[A-Za-z0-9._%+-]++@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}/,
     "email address"},
    {~r/(?:(?<=\\[nt])|(?<![0-9A-Za-z]))(?:sk-[A-Za-z0-9_-]{20,}|bk_[A-Za-z0-9_-]{16,}|zk_[A-Za-z0-9_]{16,}|privy_app_secret_[A-Za-z0-9]{16,}|(?:TEST|LIVE)_API_KEY:[A-Za-z0-9]+:[A-Za-z0-9]+)/,
     "API key"},
    # The Open Wallet Standard's agent token, which Zerion keeps in its config: it signs without the passphrase.
    {~r/(?:(?<=\\[nt])|(?<![0-9A-Za-z]))ows_key_[A-Za-z0-9_]{16,}/, "wallet agent token"},
    {~r/(?:(?<=\\[nt])|(?<![0-9A-Za-z]))(?:0x)?[0-9a-fA-F]{64}(?![0-9A-Za-z])/,
     "32-byte hex value: a private key or a hash"},
    # `n`, `r` and `t` are base58 letters too, so an escape's letter is never a start.
    {~r/(?:(?<=\\[nrt])|(?<![0-9A-Za-z\\])|(?<=\\)(?![nrt]))[1-9A-HJ-NP-Za-km-z]{86,90}(?![0-9A-Za-z])/,
     "64-byte base58 value: a Solana private key or signature"},
    {~r/\[\s*(?:\d{1,3}\s*,\s*){63}\d{1,3}\s*\]/, "Solana private key"}
  ]

  # A picture written out as base64: its start (BMP's carries its size, and
  # AVIF's and HEIC's a box length, before the fixed part), then at least 100
  # more of its characters, read possessively so a picture of any size is matched whole.
  # Its lines may break as written (`\n`) or escaped inside JSON, once or more
  # (`\\n`, a `/` as `\\/`), and it may follow such an escape. It may use
  # the web-safe alphabet, `-` and `_` for `+` and `/`. It takes a line after
  # a break, indented or not, only when the rest of that line is base64 and not
  # a `0x` hex value (an address, key or hash keeps its own rule), so the line
  # after a picture is never cut short, and padding ends it.
  @picture ~r"(?:(?<=\\[nrt])|(?<![A-Za-z0-9+/\\]))(?:iVBORw0KGg|(?:\\*/|_)9j(?:\\*/|_)|R0lGOD|UklGR|Qk(?:[A-Za-z0-9+_-]|\\*/){6}AAAA|SUkqA|TU0AK|AAAA(?:[A-Za-z0-9+_-]|\\*/){2}Z0eXB(?:hdmlm|oZWlj|oZWl4|taWYx)|PHN2Z|PD94bWw|JVBERi0)(?=(?:[A-Za-z0-9+/_-]|\\+/|\\+[rnt]|[ \t]|\r?\n){100})(?:[A-Za-z0-9+/_-]++|\\+/|(?:(?:\\+[rn])++|[\r\n]++)(?:[ \t]|\\+t)*+(?!0x[0-9a-fA-F]++(?:\\+[rn]|[\r\n]|\\*\"|$))(?=(?:[A-Za-z0-9+/_-]++|\\+/)++=*+(?:\\+[rn]|[\r\n]|\\*\"|$)))*+=*"

  # Each escaped `/` or line of a picture is one more step of the match, and
  # the default step limit ends a match silently; ten steps a byte covers any
  # text, and a text that still reaches the limit raises rather than keep a secret.
  @steps_per_byte 10

  @type known :: {value :: String.t(), label :: String.t()}

  @doc """
  The known secrets of a turn: model and operator keys, and each value in
  `secrets.py`'s answer labelled with the kind of file it came from.
  """
  @spec known(String.t() | nil, [%{String.t() => term()}], [String.t() | nil]) :: [known()]
  def known(model_key, files, operator_keys \\ []) do
    from_files =
      for %{"path" => path, "values" => values} <- files, value <- values do
        {value, kind(path) <> ", from " <> path}
      end

    keys =
      [model_key | operator_keys]
      |> Enum.filter(&(is_binary(&1) and &1 != ""))
      |> Enum.map(&{&1, "API key"})

    keys ++ from_files
  end

  @doc """
  The site's own secrets that could reach a machine's output or an error: the
  model key sent to each attempt, the Bankr key, the Sprites token, the
  evidence store's secret and the funder's key. Failure text and command errors
  are blanked against these as well as by shape, so a key without a vendor
  prefix, or written without its 0x, cannot stay in them.
  """
  @spec site_known() :: [known()]
  def site_known do
    known(
      Application.get_env(:techtree, Techtree.WalletBench, [])[:model_key],
      [],
      [
        Application.get_env(:techtree, :wallet_bench_bankr_api_key),
        Application.get_env(:regent_sprites, :token),
        Application.get_env(:techtree, Techtree.WalletBench.Evidence, [])[:secret_access_key]
        | funder_key_forms(System.get_env("WALLETBENCH_FUNDER_KEY"))
      ]
    )
  end

  @doc """
  The last `bytes` of `text`, cut only after it is blanked, so a secret that
  straddles the cut leaves none of itself behind. A window fetched for this
  should start more than the longest secret before the cut
  (`Techtree.WalletBench.Remote.job_log_tail/3`).
  """
  @spec last(String.t(), [known()], pos_integer()) :: String.t()
  def last(text, known, bytes) do
    blanked = text |> String.replace_invalid() |> blank(known)

    if byte_size(blanked) <= bytes,
      do: blanked,
      else: blanked |> binary_part(byte_size(blanked) - bytes, bytes) |> String.replace_invalid()
  end

  @doc """
  The last `bytes` of a window read `margin` bytes past the cut, blanked first.
  A window that came back full may start inside a secret; blanking can shrink
  what follows, so no more is kept than lies past the margin once blanked.
  """
  @spec last_of_window(String.t(), [known()], pos_integer(), pos_integer()) :: String.t()
  def last_of_window(window, known, bytes, margin) when byte_size(window) < bytes + margin,
    do: last(window, known, bytes)

  def last_of_window(window, known, bytes, margin) do
    blanked = window |> String.replace_invalid() |> blank(known)

    case min(bytes, byte_size(blanked) - margin) do
      keep when keep > 0 ->
        blanked |> binary_part(byte_size(blanked) - keep, keep) |> String.replace_invalid()

      _none ->
        ""
    end
  end

  @doc """
  Blanks every known secret, then every picture, then every pattern, in
  `text`. Known secrets go first, so a picture's match never takes the start
  of one and leaves the rest.
  """
  @spec blank(String.t(), [known()]) :: String.t()
  def blank(text, known) do
    known
    |> Enum.flat_map(fn {value, label} -> Enum.map(forms(value), &{&1, label}) end)
    |> Enum.sort_by(fn {value, _label} -> -byte_size(value) end)
    |> Enum.reduce(text, fn {value, label}, text -> String.replace(text, value, mark(label)) end)
    |> blank_all(@picture, "picture")
    |> blank_patterns()
    |> blank_phrases()
  end

  defp blank_all(text, regex, label) do
    steps = max(10_000_000, @steps_per_byte * byte_size(text))
    options = Regex.opts(regex) ++ [:global, :report_errors, match_limit: steps, capture: :first]

    case :re.run(text, Regex.source(regex), options) do
      :nomatch ->
        text

      {:match, found} ->
        {kept, from} =
          Enum.reduce(found, {[], 0}, fn [{at, length}], {kept, from} ->
            {[kept, binary_part(text, from, at - from), mark(label)], at + length}
          end)

        IO.iodata_to_binary([kept, binary_part(text, from, byte_size(text) - from)])

      {:error, reason} ->
        raise "Blanking stopped at the #{label} rule (#{inspect(reason)}), so this text is not kept."
    end
  end

  # The funder's key as configured and, without its 0x, as bare hex; only a key
  # of the shape the funder accepts, so a stray short value blanks nothing else.
  defp funder_key_forms("0x" <> hex = key) when byte_size(hex) == 64 do
    if hex =~ ~r/\A[0-9a-fA-F]{64}\z/, do: [key, hex], else: []
  end

  defp funder_key_forms(_key), do: []

  defp forms(value) do
    escaped = value |> Jason.encode!() |> String.slice(1..-2//1)
    Enum.uniq([value, escaped])
  end

  defp kind(path) do
    cond do
      path =~ ~r/pass(word|phrase)?/i -> "password"
      path =~ ~r/mnemonic|seed|recovery/i -> "recovery secret"
      path =~ ~r/keystore/i -> "keystore"
      path =~ ~r/priv|\.key$|\.pem$/i -> "private key"
      path =~ ~r/token/i -> "token"
      true -> "secret file contents"
    end
  end

  defp blank_patterns(text) do
    Enum.reduce(@patterns, text, fn {pattern, label}, text -> blank_all(text, pattern, label) end)
  end

  # A run of recovery-phrase words, in any case: consecutive list words
  # separated only by spaces (any kind), line breaks or tabs (also escaped once
  # or more, as in JSON inside JSON), a word's number, the quotes, commas and
  # brackets of a list, or a `-`, `|`, `/`, `_`, `.`, `;` or `+`.
  defp blank_phrases(text) do
    # A word starts after a non-letter, or right after a `\n`, `\r` or `\t` escape.
    ~r/(?:(?<=\\[nrt])|(?<![A-Za-z\\]))[A-Za-z]{3,8}(?![A-Za-z])/
    |> Regex.scan(text, return: :index)
    |> Enum.map(fn [{at, length}] -> {at, length} end)
    |> runs(text, [], [])
    # Runs come last first, so blanking one never moves the next.
    |> Enum.filter(&(length(&1) >= @phrase_length))
    |> Enum.reduce(text, fn run, text ->
      {first, _length} = List.last(run)
      {last, length} = hd(run)
      stop = last + length

      binary_part(text, 0, first) <>
        mark("recovery phrase") <> binary_part(text, stop, byte_size(text) - stop)
    end)
  end

  defp runs([], _text, run, done), do: [run | done]

  defp runs([{at, length} = word | rest], text, run, done) do
    cond do
      not MapSet.member?(@words, String.downcase(binary_part(text, at, length))) ->
        runs(rest, text, [], [run | done])

      run == [] or joined?(text, hd(run), word) ->
        runs(rest, text, [word | run], done)

      true ->
        runs(rest, text, [word], [run | done])
    end
  end

  defp joined?(text, {at, length}, {next, _length}) do
    gap = binary_part(text, at + length, next - at - length)
    gap =~ ~r/\A(?:\s|\\+[nrt"\/]|\d{1,2}[.):\-]|[,"'\[\]\-|\/_.;+])+\z/u
  end

  defp mark(label), do: "[redacted: " <> label <> "]"
end
