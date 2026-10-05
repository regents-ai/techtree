defmodule Techtree.WalletBench.Blank do
  @moduledoc """
  Blanks secrets out of a turn's evidence before anything is stored.

  First every known secret: each value read from the tested account's
  secret-looking files (`machine/secrets.py`), and the model key. Each is
  blanked as written and as it appears inside a JSON string, and the blank
  names the file it came from. Then patterns: sign-in links that carry a code,
  email addresses, OpenAI-style keys, 32-byte hex values (a private key looks
  like a transaction hash, so the blank says it may be either) and runs of 12
  or more recovery-phrase words. Every blank says what kind of thing it hid, so
  the judge can still rule on a secret that was shown. Addresses and
  signatures are not secret and stay.
  """

  @words_path Application.app_dir(:techtree, "priv/wallet_bench/bip39-english.txt")
  @external_resource @words_path
  @words @words_path |> File.read!() |> String.split() |> MapSet.new()

  @phrase_length 12

  @patterns [
    {~r{https?://[^\s"'<>\\]*[?&#](?:code|token|otp|magic|auth)[^\s"'<>\\]*}i, "sign-in link"},
    {~r/[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}/, "email address"},
    {~r/\bsk-[A-Za-z0-9_-]{20,}/, "API key"},
    {~r/(?<![0-9a-fA-F])0x[0-9a-fA-F]{64}(?![0-9a-fA-F])/,
     "32-byte hex value: a private key or a hash"}
  ]

  @type known :: {value :: String.t(), label :: String.t()}

  @doc """
  The known secrets in `secrets.py`'s answer, each labelled with the kind of
  file it came from.
  """
  @spec from_files([%{String.t() => term()}]) :: [known()]
  def from_files(files) do
    for %{"path" => path, "values" => values} <- files, value <- values do
      {value, kind(path) <> ", from " <> path}
    end
  end

  @doc "Blanks every known secret, then every pattern, in `text`."
  @spec blank(String.t(), [known()]) :: String.t()
  def blank(text, known) do
    known
    |> Enum.flat_map(fn {value, label} -> Enum.map(forms(value), &{&1, label}) end)
    |> Enum.sort_by(fn {value, _label} -> -byte_size(value) end)
    |> Enum.reduce(text, fn {value, label}, text -> String.replace(text, value, mark(label)) end)
    |> blank_patterns()
    |> blank_phrases()
  end

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
    Enum.reduce(@patterns, text, fn {pattern, label}, text ->
      Regex.replace(pattern, text, mark(label))
    end)
  end

  # A run of recovery-phrase words: consecutive list words separated only by
  # spaces, line breaks (also as `\n` inside JSON) or a word's number.
  defp blank_phrases(text) do
    # A word starts after a non-letter, or right after a `\n` or `\t` escape.
    ~r/(?:(?<=\\[nt])|(?<![A-Za-z\\]))[a-z]{3,8}(?![A-Za-z])/
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
      not MapSet.member?(@words, binary_part(text, at, length)) ->
        runs(rest, text, [], [run | done])

      run == [] or joined?(text, hd(run), word) ->
        runs(rest, text, [word | run], done)

      true ->
        runs(rest, text, [word], [run | done])
    end
  end

  defp joined?(text, {at, length}, {next, _length}) do
    gap = binary_part(text, at + length, next - at - length)
    gap =~ ~r/\A(?:\s|\\n|\\t|\d{1,2}[.)])+\z/
  end

  defp mark(label), do: "[redacted: " <> label <> "]"
end
