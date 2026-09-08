defmodule Techtree.Network.AgentVersions do
  @moduledoc """
  Selection and ordering of agent versions represented in accepted publications.

  Release versions use semantic precedence, never arrival order. Opaque build
  identifiers remain selectable, after releases, in first-seen order. Their
  labels are preserved verbatim; an upload is not evidence of release precedence.
  """

  def families(entries) do
    entries
    |> Enum.group_by(& &1.subject_harness)
    |> Enum.map(fn {id, entries} ->
      versions =
        entries
        |> Enum.sort(&newer?/2)
        |> Enum.map(& &1.subject_harness_version)
        |> Enum.uniq()

      %{id: id, label: label(id), versions: versions}
    end)
    |> Enum.sort_by(fn family -> {family.id != "hermes-agent", family.label, family.id} end)
  end

  def select([], params) do
    if Map.has_key?(params, "agent") or Map.has_key?(params, "agent_version"),
      do: {:error, "No published Results match that agent and version."},
      else: {:ok, nil}
  end

  def select(families, params) do
    id = Map.get(params, "agent", hd(families).id)

    with %{versions: versions} = family <- Enum.find(families, &(&1.id == id)),
         version when is_binary(version) <- Map.get(params, "agent_version", hd(versions)),
         true <- version in versions do
      index = Enum.find_index(versions, &(&1 == version))

      {:ok,
       %{
         family: family,
         version: version,
         latest: hd(versions),
         newer: if(index > 0, do: Enum.at(versions, index - 1)),
         older: Enum.at(versions, index + 1)
       }}
    else
      _ -> {:error, "No published Results match that agent and version."}
    end
  end

  def url(agent, version, options \\ []) do
    params = [{"agent", agent}, {"agent_version", version}]

    params =
      Enum.reduce([:model, :challenge, :before_sequence, :limit], params, fn key, params ->
        case Keyword.get(options, key) do
          nil -> params
          value -> params ++ [{to_string(key), to_string(value)}]
        end
      end)

    "/results?" <> URI.encode_query(params)
  end

  defp label("hermes-agent"), do: "Hermes"
  defp label("prime-agent"), do: "Prime Agent"
  defp label("codex"), do: "Codex"
  defp label(id), do: id

  defp newer?(left, right) do
    a = left.subject_harness_version
    b = right.subject_harness_version

    case {release(a), release(b)} do
      {{:ok, av}, {:ok, bv}} ->
        case Version.compare(av, bv) do
          :eq -> a >= b
          :gt -> true
          :lt -> false
        end

      {{:ok, _}, :error} ->
        true

      {:error, {:ok, _}} ->
        false

      {:error, :error} ->
        {left.log_sequence, a} >= {right.log_sequence, b}
    end
  end

  # Strip a conventional tag prefix for comparison only, never for identity.
  defp release("v" <> version), do: Version.parse(version)
  defp release(version), do: Version.parse(version)
end
