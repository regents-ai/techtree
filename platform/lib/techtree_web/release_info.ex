defmodule TechtreeWeb.ReleaseInfo do
  @moduledoc """
  The one active release coordinate the public pages may present.

  Installation copy is derived from the bootstrap payload selected by the Ash
  release pointer. Pages never carry a second CLI version or reconstruct an
  install command independently.
  """

  alias Techtree.Catalog.Query

  @type t :: %{
          digest: String.t(),
          install_argv: [String.t()],
          installable?: boolean(),
          minimums: map(),
          source_revision: String.t() | nil,
          version: String.t() | nil
        }

  @doc """
  Return the active bootstrap release as display data, or `nil` when no release
  is published.

  A placeholder remains visible as release state but is never presented as an
  executable command.
  """
  @spec current() :: t() | nil
  def current do
    with {:ok, instructions, digest} <- Query.bootstrap_instructions_with_digest() do
      cli = Map.get(instructions, "cli", %{})

      %{
        digest: digest,
        install_argv: Map.get(cli, "install_argv", []),
        installable?: instructions["placeholder_release"] == false,
        minimums: Map.get(instructions, "minimums", %{}),
        source_revision: cli["source_revision"],
        version: cli["version"]
      }
    else
      _error -> nil
    end
  end

  @doc """
  The short compatibility sentence shown beside the active installer.
  """
  @spec compatibility(t()) :: String.t()
  def compatibility(%{minimums: minimums}) do
    python = Map.get(minimums, "python")
    docker = if minimums["docker_required"] == true, do: "Docker required", else: "No Docker"
    hermes = Map.get(minimums, "hermes_version")

    [
      "macOS or Linux",
      "x86_64 or arm64",
      python && "Python #{python}+",
      docker,
      hermes && "Hermes #{hermes}+ optional"
    ]
    |> Enum.reject(&is_nil/1)
    |> Enum.join(" · ")
  end

  @doc """
  A compact immutable release label.
  """
  @spec label(t()) :: String.t()
  def label(release) do
    "v#{release.version} · #{short(release.digest)}"
  end

  defp short("sha256:" <> digest), do: "sha256:" <> String.slice(digest, 0, 12) <> "…"
  defp short(digest), do: digest
end
