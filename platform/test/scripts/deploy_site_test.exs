defmodule Techtree.DeploySiteScriptTest do
  @moduledoc """
  scripts/deploy_site.sh refuses to deploy unless it can name the live image
  (whose files the new release keeps) and the live page's script, and fails
  unless that script still answers after the deploy. Each case runs the real
  script in a throwaway pushed checkout, with stand-ins for flyctl, curl and
  rsync on its PATH, so nothing reaches Fly or the site.
  """
  use ExUnit.Case, async: true

  @moduletag :tmp_dir

  # Each test's throwaway folder goes when the test does.
  setup %{tmp_dir: dir} do
    on_exit(fn -> File.rm_rf!(dir) end)
  end

  @script Path.expand("../../scripts/deploy_site.sh", __DIR__)
  @live "registry.fly.io/techtree-sh@sha256:" <> String.duplicate("ab", 32)
  @page ~s(<script src="/assets/js/site-0123abcd.js?vsn=d"></script>)

  # A clean checkout holding the script, pushed to its upstream, as the script requires.
  defp checkout(dir) do
    repo = Path.join(dir, "repo")
    File.mkdir_p!(Path.join(repo, "platform/scripts"))
    File.cp!(@script, Path.join(repo, "platform/scripts/deploy_site.sh"))

    File.write!(
      Path.join(repo, ".gitignore"),
      "platform/blog_content/\nplatform/skills_content/\n"
    )

    git = fn args -> {_, 0} = System.cmd("git", args, cd: repo, stderr_to_stdout: true) end
    {_, 0} = System.cmd("git", ["init", "-q", "--bare", Path.join(dir, "origin.git")])
    git.(["init", "-q", "-b", "release"])
    git.(["-c", "user.name=t", "-c", "user.email=t@t", "add", "."])
    git.(["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "release"])
    git.(["remote", "add", "origin", Path.join(dir, "origin.git")])
    git.(["push", "-q", "-u", "origin", "release"])
    repo
  end

  # Stand-ins: flyctl answers `image show` from image.json and records `deploy`;
  # curl answers the home page from home.html and the old script with its status.
  defp fakes(dir, scenario) do
    bin = Path.join(dir, "bin")
    File.mkdir_p!(bin)
    File.write!(Path.join(dir, "image.json"), scenario[:image])
    File.write!(Path.join(dir, "home.html"), scenario[:page])

    stand_in = fn name, body ->
      File.write!(Path.join(bin, name), "#!/usr/bin/env bash\n" <> body)
      File.chmod!(Path.join(bin, name), 0o755)
    end

    stand_in.("flyctl", """
    case "$1" in
      image) #{if scenario[:image_fails], do: "exit 1", else: ~s(cat "$FAKE_DIR/image.json")} ;;
      deploy) echo "$@" >> "$FAKE_DIR/deploys"; exit #{scenario[:deploy_exit] || 0} ;;
    esac
    """)

    stand_in.("curl", """
    for arg in "$@"; do url="$arg"; done
    case "$url" in
      https://techtree.sh/) cat "$FAKE_DIR/home.html" ;;
      *) echo "$url" >> "$FAKE_DIR/asked"; exit #{scenario[:old_script_exit] || 0} ;;
    esac
    """)

    stand_in.("rsync", "exit 0\n")
    bin
  end

  defp deploy(dir, scenario) do
    repo = checkout(dir)
    bin = fakes(dir, Map.merge(%{image: Jason.encode!([image(@live)]), page: @page}, scenario))

    System.cmd("bash", [Path.join(repo, "platform/scripts/deploy_site.sh")],
      env: [{"PATH", bin <> ":" <> System.get_env("PATH")}, {"FAKE_DIR", dir}],
      stderr_to_stdout: true
    )
  end

  defp image(ref) do
    [registry, rest] = String.split(ref, "/", parts: 2)
    [repository, digest] = String.split(rest, "@")
    %{"Registry" => registry, "Repository" => repository, "Digest" => digest}
  end

  defp deployed(dir), do: File.read(Path.join(dir, "deploys"))

  test "the live image is passed to the build, and the old script is asked for after", %{
    tmp_dir: dir
  } do
    assert {output, 0} = deploy(dir, %{})
    assert {:ok, deploys} = deployed(dir)
    assert deploys =~ "--build-arg PREVIOUS_IMAGE=#{@live}"
    assert File.read!(Path.join(dir, "asked")) =~ "https://techtree.sh/assets/js/site-0123abcd.js"
    assert output =~ "The previous release's /assets/js/site-0123abcd.js still answers."
  end

  test "no deploy when the live image can't be read", %{tmp_dir: dir} do
    for scenario <- [
          %{image_fails: true},
          %{image: "[]"},
          %{
            image:
              Jason.encode!([
                image("registry.fly.io/patchbay@sha256:" <> String.duplicate("cd", 32))
              ])
          },
          %{image: Jason.encode!([image("registry.fly.io/techtree-sh@deployment-01ABC")])}
        ] do
      case_dir = Path.join(dir, Integer.to_string(:erlang.unique_integer([:positive])))

      assert {output, status} = deploy(case_dir, scenario)
      assert status != 0
      assert output =~ "Refusing to deploy: the live image can't be read"
      assert deployed(case_dir) == {:error, :enoent}
    end
  end

  test "no deploy when the machines run different images", %{tmp_dir: dir} do
    other = "registry.fly.io/techtree-sh@sha256:" <> String.duplicate("ef", 32)

    assert {output, status} =
             deploy(dir, %{image: Jason.encode!([image(@live), image(other), image(@live)])})

    assert status != 0
    assert output =~ "Refusing to deploy: the machines run different images"
    assert output =~ other
    assert deployed(dir) == {:error, :enoent}
  end

  test "machines on the same image deploy as one", %{tmp_dir: dir} do
    assert {_output, 0} = deploy(dir, %{image: Jason.encode!([image(@live), image(@live)])})
    assert {:ok, deploys} = deployed(dir)
    assert deploys =~ "--build-arg PREVIOUS_IMAGE=#{@live}"
  end

  test "no deploy when the live page names no script to check afterwards", %{tmp_dir: dir} do
    assert {output, status} = deploy(dir, %{page: "<html>no script</html>"})
    assert status != 0
    assert output =~ "Refusing to deploy: the live page names no script"
    assert deployed(dir) == {:error, :enoent}
  end

  # The build pulls the previous image; when that fails, so does the deploy.
  test "a failed build stops the script before any after-check", %{tmp_dir: dir} do
    assert {output, status} = deploy(dir, %{deploy_exit: 1})
    assert status != 0
    refute output =~ "still answers"
    refute File.exists?(Path.join(dir, "asked"))
  end

  test "the deploy fails when the old script does not answer after it", %{tmp_dir: dir} do
    assert {output, status} = deploy(dir, %{old_script_exit: 22})
    assert status != 0
    assert output =~ "does not answer"
  end
end
