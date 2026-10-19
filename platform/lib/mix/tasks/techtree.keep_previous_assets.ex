defmodule Mix.Tasks.Techtree.KeepPreviousAssets do
  @shortdoc "Copies the previous release's served files into this release, beside its own"
  @moduledoc """
      mix techtree.keep_previous_assets PREVIOUS_LIB RELEASE_LIB

  While a deploy rolls over, a page served by the old machine asks the new one
  for the files that page was built with. This copies those files into the new
  release so they still answer: every file the previous release's
  `cache_manifest.json` lists (each digested name and its plain name), with its
  compressed copy.

  `PREVIOUS_LIB` and `RELEASE_LIB` are the `lib` folders of the previous and
  the new release. Only files the previous manifest lists are copied, one release
  back, and nothing already in the new release is replaced. Without a previous
  manifest it stops with an error: a release is never built without them.
  """
  use Mix.Task

  @impl Mix.Task
  def run([previous_lib, release_lib]) do
    copied = keep(static!(previous_lib), static!(release_lib))
    Mix.shell().info("Kept #{length(copied)} files from the previous release.")
  end

  def run(_args),
    do: Mix.raise("Usage: mix techtree.keep_previous_assets PREVIOUS_LIB RELEASE_LIB")

  @doc """
  Copies every file `previous`'s manifest lists into `current` (both `priv/static`
  folders) that `current` does not already have. Returns the copied paths.
  """
  @spec keep(Path.t(), Path.t()) :: [String.t()]
  def keep(previous, current) do
    manifest = Path.join(previous, "cache_manifest.json")

    unless File.regular?(manifest),
      do: Mix.raise("The previous release has no #{manifest}; its files can't be kept.")

    %{"digests" => digests} = manifest |> File.read!() |> Jason.decode!()

    for {digested, %{"logical_path" => logical}} <- digests,
        path <- [digested, logical],
        file <- [path, path <> ".gz"],
        File.regular?(Path.join(previous, file)),
        not File.exists?(Path.join(current, file)),
        uniq: true do
      File.mkdir_p!(Path.dirname(Path.join(current, file)))
      File.cp!(Path.join(previous, file), Path.join(current, file))
      file
    end
  end

  defp static!(lib) do
    case Path.wildcard(Path.join(lib, "techtree-*/priv/static")) do
      [static] -> static
      found -> Mix.raise("Expected one Techtree release in #{lib}, found #{length(found)}.")
    end
  end
end
