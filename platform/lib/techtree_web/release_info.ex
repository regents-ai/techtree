defmodule TechtreeWeb.ReleaseInfo do
  @moduledoc """
  The one active release the public pages may present, read for display.

  Every installation coordinate a page shows comes from here, and here reads
  the exact published bytes the site serves — never a value written into a
  template. A page therefore cannot show a version, a fingerprint, or a command
  that this release does not publish, and it cannot pair one release's command
  with another release's fingerprint: both come out of the same read.

  When the published contract says its coordinates are stand-ins, that is
  release state a page may describe, and never something a page offers as a
  command to run or an address to follow.
  """

  alias Techtree.Catalog.Query

  @type t :: %{
          channel: String.t() | nil,
          digest: String.t(),
          install_argv: [String.t()],
          installable?: boolean(),
          introductory_reference: String.t() | nil,
          minimums: map(),
          plugin_doctor_argv: [String.t()],
          plugin_install_argv: [String.t()],
          repository_url: String.t() | nil,
          source_revision: String.t() | nil,
          starter_skill: map(),
          version: String.t() | nil
        }

  @unset_revision String.duplicate("0", 40)

  @doc """
  The active release as display data, or `nil` when nothing is published.
  """
  @spec current() :: t() | nil
  def current do
    with {:ok, payload, digest} <- Query.bootstrap_payload(),
         {:ok, instructions} when is_map(instructions) <- Jason.decode(payload) do
      describe(instructions, digest)
    else
      _error -> nil
    end
  end

  @doc """
  The short compatibility sentence shown beside the active installer.

  Every clause is read from the published contract. Nothing is claimed about a
  platform the contract does not name.
  """
  @spec compatibility(t()) :: String.t()
  def compatibility(%{minimums: minimums}) do
    [
      "macOS or Linux",
      python_words(minimums["python"]),
      docker_words(minimums["docker_required"]),
      hermes_words(minimums["hermes_version"])
    ]
    |> Enum.reject(&is_nil/1)
    |> Enum.join(" · ")
  end

  @doc """
  A compact release label: the version, and the first characters of the
  fingerprint of the exact contract those coordinates were read from.
  """
  @spec label(t()) :: String.t()
  def label(release), do: "v#{release.version} · #{short(release.digest)}"

  # The plugin release as an address, or nothing at all. A stand-in revision
  # and a branch name are both addresses that either point at nothing or point
  # somewhere different tomorrow, so neither is ever shown.
  defp repository_url(instructions) do
    repository = get_in(instructions, ["hermes_plugin", "repository"])
    revision = get_in(instructions, ["hermes_plugin", "revision"])

    if instructions["placeholder_release"] == false and is_binary(repository) and
         pinned?(revision) do
      "https://github.com/" <> repository <> "/tree/" <> revision
    end
  end

  defp describe(instructions, digest) do
    cli = Map.get(instructions, "cli", %{})
    hermes_plugin = Map.get(instructions, "hermes_plugin", %{})

    %{
      channel: instructions["channel"],
      digest: digest,
      install_argv: Map.get(cli, "install_argv", []),
      installable?: instructions["placeholder_release"] == false,
      introductory_reference: get_in(instructions, ["introductory_climb", "reference"]),
      minimums: Map.get(instructions, "minimums", %{}),
      plugin_doctor_argv: Map.get(hermes_plugin, "doctor_argv", []),
      plugin_install_argv: Map.get(hermes_plugin, "install_argv", []),
      repository_url: repository_url(instructions),
      source_revision: cli["source_revision"],
      starter_skill: Map.get(instructions, "starter_skill", %{}),
      version: cli["version"]
    }
  end

  defp pinned?(revision) when is_binary(revision) do
    String.match?(revision, ~r/\A[0-9a-f]{40}\z/) and revision != @unset_revision
  end

  defp pinned?(_revision), do: false

  defp python_words(nil), do: nil
  defp python_words(version), do: "Python #{version}, provided by the installer"

  defp docker_words(true), do: "Docker required"
  defp docker_words(_other), do: nil

  defp hermes_words(nil), do: nil
  defp hermes_words(version), do: "Hermes #{version}+ for the plugin path"

  defp short("sha256:" <> digest), do: "sha256:" <> String.slice(digest, 0, 12) <> "…"
  defp short(digest), do: digest
end
