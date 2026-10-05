defmodule Techtree.WalletBench.Catalog do
  @moduledoc """
  What the bench can test, read from `priv/wallet_bench/`: the harnesses and
  wallets it knows, the survey's prompts and review guides, the wallets' notes,
  and the recipe pack a machine's baseline is built from.

  The pack holds `machine/` and the harness's own folder. Its digest is the
  sha256 of a `sha256sum`-style list of every file in it, so it names the exact
  scripts a baseline carries, whatever the files' dates.
  """

  @harnesses %{"H05" => %{id: "H05", name: "Claude Code"}}

  @wallets %{
    "W07" => %{
      id: "W07",
      name: "Foundry Cast",
      executable: "cast",
      help: ["--help"],
      survey_version: "1.8.3"
    }
  }

  @tests [:T1a, :T1b, :T2, :T2_signature]

  # The survey's watchdogs, in seconds.
  @wall_caps %{T1a: 1800, T1b: 1800, T2: 1800, T2_signature: 900}

  @type harness :: %{id: String.t(), name: String.t()}
  @type wallet :: %{
          id: String.t(),
          name: String.t(),
          executable: String.t(),
          help: [String.t()],
          survey_version: String.t()
        }

  @doc "The harness ids the bench can build."
  @spec harness_ids() :: [String.t()]
  def harness_ids, do: Map.keys(@harnesses)

  @doc "The wallet ids the bench can test."
  @spec wallet_ids() :: [String.t()]
  def wallet_ids, do: Map.keys(@wallets)

  @doc "The tests, in the order they can run."
  @spec tests() :: [atom()]
  def tests, do: @tests

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

  @doc "The recipe pack for a harness's machines, as a gzipped tar, and its digest."
  @spec recipe_pack(String.t()) :: {binary(), String.t()}
  def recipe_pack(harness_id) do
    files = pack_files(harness_id)
    {tar(files), digest(files)}
  end

  @doc "The digest a machine built from today's recipe carries."
  @spec recipe_digest(String.t()) :: String.t()
  def recipe_digest(harness_id), do: harness_id |> pack_files() |> digest()

  defp pack_files(harness_id) do
    root = root()

    ["machine", "harness/" <> Map.fetch!(@harnesses, harness_id).id]
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

  defp read!(relative), do: root() |> Path.join(relative) |> File.read!()

  defp root, do: Application.app_dir(:techtree, "priv/wallet_bench")
end
