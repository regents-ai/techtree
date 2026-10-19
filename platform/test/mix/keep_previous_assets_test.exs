defmodule Mix.Tasks.Techtree.KeepPreviousAssetsTest do
  @moduledoc """
  A deploy keeps the previous release's files servable: exactly the files its
  manifest lists, never replacing the new release's own, and never built
  without them.
  """
  use ExUnit.Case, async: true

  alias Mix.Tasks.Techtree.KeepPreviousAssets

  @moduletag :tmp_dir

  # Each test's throwaway folder goes when the test does.
  setup %{tmp_dir: dir} do
    on_exit(fn -> File.rm_rf!(dir) end)
  end

  defp release(dir, name, files) do
    static = Path.join([dir, name, "techtree-0.2.0", "priv", "static"])

    for {path, body} <- files do
      File.mkdir_p!(Path.dirname(Path.join(static, path)))
      File.write!(Path.join(static, path), body)
    end

    Path.join(dir, name)
  end

  defp manifest(digests) do
    Jason.encode!(%{
      "version" => 1,
      "latest" => %{},
      "digests" =>
        Map.new(digests, fn {digested, logical} -> {digested, %{"logical_path" => logical}} end)
    })
  end

  test "the previous release's listed files are added, its own unlisted ones are not", %{
    tmp_dir: dir
  } do
    previous =
      release(dir, "previous", %{
        "cache_manifest.json" =>
          manifest(%{
            "assets/js/site-aaa.js" => "assets/js/site.js",
            "assets/chunk-OLD-bbb.js" => "assets/chunk-OLD.js"
          }),
        "assets/js/site-aaa.js" => "old site",
        "assets/js/site-aaa.js.gz" => "old site, compressed",
        "assets/js/site.js" => "old site",
        "assets/chunk-OLD-bbb.js" => "old chunk",
        "assets/chunk-OLD.js" => "old chunk",
        "assets/unlisted.js" => "not in the manifest"
      })

    current =
      release(dir, "current", %{
        "assets/js/site.js" => "new site",
        "assets/js/site-ccc.js" => "new site"
      })

    Mix.Task.rerun("techtree.keep_previous_assets", [previous, current])
    static = Path.join(current, "techtree-0.2.0/priv/static")

    assert File.read!(Path.join(static, "assets/js/site-aaa.js")) == "old site"
    assert File.read!(Path.join(static, "assets/js/site-aaa.js.gz")) == "old site, compressed"
    assert File.read!(Path.join(static, "assets/chunk-OLD.js")) == "old chunk"
    assert File.read!(Path.join(static, "assets/chunk-OLD-bbb.js")) == "old chunk"

    # The new release's own files stay as built.
    assert File.read!(Path.join(static, "assets/js/site.js")) == "new site"
    refute File.exists?(Path.join(static, "assets/unlisted.js"))
  end

  test "a previous release with no manifest stops the build", %{tmp_dir: dir} do
    previous = release(dir, "previous", %{"assets/js/site-aaa.js" => "old site"})
    current = release(dir, "current", %{"assets/js/site.js" => "new site"})

    assert_raise Mix.Error, ~r/has no .*cache_manifest.json/, fn ->
      KeepPreviousAssets.run([previous, current])
    end
  end

  # Two releases in one image is never the one release to keep files from.
  test "two previous releases stop the build", %{tmp_dir: dir} do
    previous = release(dir, "previous", %{"cache_manifest.json" => manifest(%{})})
    File.mkdir_p!(Path.join(previous, "techtree-0.1.0/priv/static"))
    current = release(dir, "current", %{"assets/js/site.js" => "new site"})

    assert_raise Mix.Error, ~r/Expected one Techtree release in .*, found 2/, fn ->
      KeepPreviousAssets.run([previous, current])
    end
  end

  # The previous image couldn't be pulled, so there is no previous release to read.
  test "no previous release at all stops the build", %{tmp_dir: dir} do
    current = release(dir, "current", %{"assets/js/site.js" => "new site"})

    assert_raise Mix.Error, ~r/Expected one Techtree release in .*, found 0/, fn ->
      KeepPreviousAssets.run([Path.join(dir, "missing"), current])
    end
  end
end
