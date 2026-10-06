defmodule Techtree.WalletBench.Catalog do
  @moduledoc """
  What the bench can test, read from `priv/wallet_bench/`: the harnesses and
  wallets it knows, the survey's prompts and review guides, the wallets' notes,
  and the recipe pack every machine's baseline is built from.

  Eight wallets are listed with a fixed result and never run (founder
  decisions 2 b and 4 b, 6 October 2026): six need a person to sign in, one
  cannot run on a server and one makes no keys. Cline takes the install tests
  only, because it cannot continue a conversation from a script (5 a).

  The pack holds `machine/` and `runner/`. Its digest is the sha256 of a
  `sha256sum`-style list of every file in it, so it names the exact scripts a
  baseline carries, whatever the files' dates.
  """

  @install_tests [:T1a, :T1b]

  @harnesses Map.new(
               [
                 %{id: "H04", name: "Hermes Agent", tests: [:T1a, :T1b, :T2, :T2_signature]},
                 %{id: "H05", name: "Claude Code", tests: [:T1a, :T1b, :T2, :T2_signature]},
                 %{id: "H06", name: "Cline", tests: @install_tests},
                 %{id: "H07", name: "Kilo Code", tests: [:T1a, :T1b, :T2, :T2_signature]},
                 %{id: "H08", name: "Pi", tests: [:T1a, :T1b, :T2, :T2_signature]},
                 %{id: "H09", name: "oh-my-pi", tests: [:T1a, :T1b, :T2, :T2_signature]},
                 %{id: "H10", name: "Codex CLI", tests: [:T1a, :T1b, :T2, :T2_signature]},
                 %{id: "H12", name: "DeepSeek Harness", tests: [:T1a, :T1b, :T2, :T2_signature]},
                 %{id: "H13", name: "OpenCode", tests: [:T1a, :T1b, :T2, :T2_signature]}
               ],
               &{&1.id, &1}
             )

  @wallets Map.new(
             [
               %{
                 id: "W01",
                 name: "Bankr",
                 executable: "bankr",
                 survey_version: "0.3.43",
                 fixed: nil
               },
               %{
                 id: "W02",
                 name: "MetaMask Agent Wallet",
                 executable: "mm",
                 survey_version: "7.0.0",
                 fixed: %{
                   outcome: "WAITING_HUMAN",
                   reason: "Signing in needs a person in a browser, or MetaMask Mobile."
                 }
               },
               %{
                 id: "W03",
                 name: "MoonPay",
                 executable: "mp",
                 survey_version: "1.96.5",
                 fixed: nil
               },
               %{
                 id: "W05",
                 name: "Coinbase Agentic Wallet",
                 executable: "awal",
                 survey_version: "2.12.1",
                 fixed: %{outcome: "NOT_RUN", reason: "It cannot run on a server."}
               },
               %{
                 id: "W06",
                 name: "Phantom",
                 executable: "phantom",
                 survey_version: "2.0.1",
                 fixed: %{
                   outcome: "WAITING_HUMAN",
                   reason:
                     "Signing in needs a person in a browser, with Google, Apple or the extension."
                 }
               },
               %{
                 id: "W07",
                 name: "Foundry Cast",
                 executable: "cast",
                 survey_version: "1.8.3",
                 fixed: nil
               },
               %{
                 id: "W09",
                 name: "Circle",
                 executable: "circle",
                 survey_version: "1.1.4",
                 fixed: %{
                   outcome: "WAITING_HUMAN",
                   reason:
                     "Signing in needs a person to accept Circle's Terms and give an emailed code."
                 }
               },
               %{
                 id: "W10",
                 name: "Safe",
                 executable: "safe-cli",
                 survey_version: "1.9.0",
                 fixed: %{outcome: "NOT_RUN", reason: "It makes no keys of its own."}
               },
               %{
                 id: "W13",
                 name: "Zerion",
                 executable: "zerion",
                 survey_version: "1.9.1",
                 fixed: nil
               },
               %{
                 id: "W14",
                 name: "Splits",
                 executable: "splits",
                 survey_version: "0.2.12",
                 fixed: %{
                   outcome: "WAITING_HUMAN",
                   reason: "It needs a person's passkey account and an API key made in a browser."
                 }
               },
               %{
                 id: "W15",
                 name: "Privy",
                 executable: "paw",
                 survey_version: "0.3.6",
                 fixed: %{
                   outcome: "WAITING_HUMAN",
                   reason: "Signing in needs a person to approve a device code in a browser."
                 }
               },
               %{
                 id: "W17",
                 name: "Turnkey",
                 executable: "turnkey",
                 survey_version: "1.1.5",
                 fixed: %{
                   outcome: "WAITING_HUMAN",
                   reason: "It needs a person's Turnkey organisation and a registered API key."
                 }
               }
             ],
             &{&1.id, Map.put(&1, :help, ["--help"])}
           )

  @tests [:T1a, :T1b, :T2, :T2_signature]

  # The survey's watchdogs, in seconds.
  @wall_caps %{T1a: 1800, T1b: 1800, T2: 1800, T2_signature: 900}

  @type harness :: %{id: String.t(), name: String.t(), tests: [atom()]}
  @type wallet :: %{
          id: String.t(),
          name: String.t(),
          executable: String.t(),
          help: [String.t()],
          survey_version: String.t(),
          fixed: nil | %{outcome: String.t(), reason: String.t()}
        }

  @doc "The harness ids the bench can build."
  @spec harness_ids() :: [String.t()]
  def harness_ids, do: Map.keys(@harnesses)

  @doc "Every wallet id the bench lists, including those with a fixed result."
  @spec wallet_ids() :: [String.t()]
  def wallet_ids, do: Map.keys(@wallets)

  @doc "The wallet ids the bench runs: those without a fixed result."
  @spec tested_wallet_ids() :: [String.t()]
  def tested_wallet_ids, do: for({id, %{fixed: nil}} <- @wallets, do: id)

  @doc "The tests, in the order they can run."
  @spec tests() :: [atom()]
  def tests, do: @tests

  @doc "The tests a harness takes, in the order they can run."
  @spec tests(String.t()) :: [atom()]
  def tests(harness_id), do: harness!(harness_id).tests

  @spec harness!(String.t()) :: harness()
  def harness!(id), do: Map.fetch!(@harnesses, id)

  @spec wallet!(String.t()) :: wallet()
  def wallet!(id), do: Map.fetch!(@wallets, id)

  @doc "The pair's name as the survey wrote it, such as `H05-W07`."
  @spec pair(String.t(), String.t()) :: String.t()
  def pair(harness_id, wallet_id), do: harness_id <> "-" <> wallet_id

  @doc "A test's folder on the machine and its name on pages."
  @spec turn_name(atom()) :: String.t()
  def turn_name(:T2_signature), do: "T2-signature"
  def turn_name(test) when test in @tests, do: Atom.to_string(test)

  @doc """
  A test's background job on the machine. The job holds a Sprites task under
  this name, and Sprites takes only lowercase letters, digits and dashes.
  """
  @spec turn_job(atom()) :: String.t()
  def turn_job(test), do: "turn-" <> String.downcase(turn_name(test))

  @spec wall_cap(atom()) :: pos_integer()
  def wall_cap(test), do: Map.fetch!(@wall_caps, test)

  @doc """
  The prompt for a test, word for word as the survey sent it. The retry prompt
  takes the error the judge quoted; the signature request names the pair.
  """
  @spec prompt(atom(), String.t(), String.t(), String.t() | nil) :: String.t()
  def prompt(:T1a, _harness_id, wallet_id, nil), do: read!("prompts/T1a/#{wallet_id}.txt")

  def prompt(:T1b, _harness_id, wallet_id, error) when is_binary(error) do
    wallet = wallet!(wallet_id)

    "prompts/T1b.txt"
    |> read!()
    |> String.replace("{wallet}", "#{wallet.name} (#{wallet.executable})")
    |> String.replace("{error}", error)
  end

  def prompt(:T2, _harness_id, _wallet_id, nil), do: read!("prompts/T2.txt")

  def prompt(:T2_signature, harness_id, wallet_id, nil) do
    "prompts/T2-signature.txt"
    |> read!()
    |> String.replace("{pair}", pair(harness_id, wallet_id))
  end

  @doc "The judge's guide for a test: `T1.md` for installs, `T2.md` for wallets."
  @spec review_guide(atom()) :: String.t()
  def review_guide(test) when test in [:T1a, :T1b], do: read!("review/T1.md")
  def review_guide(test) when test in [:T2, :T2_signature], do: read!("review/T2.md")

  @doc "What the vendor says about the wallet, for the judge."
  @spec wallet_notes(String.t()) :: String.t()
  def wallet_notes(wallet_id), do: read!("wallets/#{wallet_id}.md")

  @doc "The recipe pack every machine's baseline is built from, as a gzipped tar, and its digest."
  @spec recipe_pack() :: {binary(), String.t()}
  def recipe_pack do
    files = pack_files()
    {tar(files), digest(files)}
  end

  @doc "The digest a machine built from today's recipe carries."
  @spec recipe_digest() :: String.t()
  def recipe_digest, do: pack_files() |> digest()

  # Files under the app's own recipe folder.
  # sobelow_skip ["Traversal.FileModule"]
  defp pack_files do
    root = root()

    ["machine", "runner"]
    |> Enum.flat_map(&Path.wildcard(Path.join([root, &1, "**", "*"])))
    |> Enum.filter(&File.regular?/1)
    |> Enum.map(&{Path.relative_to(&1, root), File.read!(&1)})
    |> Enum.sort()
  end

  defp digest(files) do
    files
    |> Enum.map_join(fn {path, content} -> sha256(content) <> "  " <> path <> "\n" end)
    |> sha256()
  end

  # A file of the bench's own naming in the system's temporary folder.
  # sobelow_skip ["Traversal.FileModule"]
  defp tar(files) do
    path =
      Path.join(System.tmp_dir!(), "wallet-bench-pack-#{System.unique_integer([:positive])}.tgz")

    try do
      entries = Enum.map(files, fn {name, content} -> {String.to_charlist(name), content} end)
      :ok = :erl_tar.create(String.to_charlist(path), entries, [:compressed])
      File.read!(path)
    after
      File.rm(path)
    end
  end

  defp sha256(data), do: :crypto.hash(:sha256, data) |> Base.encode16(case: :lower)

  # Callers name files under the app's own wallet_bench folder from the catalog.
  # sobelow_skip ["Traversal.FileModule"]
  defp read!(relative), do: root() |> Path.join(relative) |> File.read!()

  defp root, do: Application.app_dir(:techtree, "priv/wallet_bench")
end
