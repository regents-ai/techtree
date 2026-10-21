defmodule Techtree.Network.AgentVersions do
  @moduledoc """
  Selection and ordering of agent versions represented in accepted publications.

  Release versions use semantic precedence, never arrival order. Opaque build
  identifiers remain selectable, after releases, in first-seen order. Their
  labels are preserved verbatim; an upload is not evidence of release precedence.
  """

  @coordinates [:agent, :agent_version, :model, :challenge, :route, :before_sequence, :limit]

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

  @doc """
  The harness and version an address chooses, if it chooses any.

  Neither chosen is every harness, and a harness alone is every version of it.
  A version without its harness, or either one with no Results, is `:error`.
  """
  def select(families, params) do
    case {Map.get(params, "agent"), Map.get(params, "agent_version")} do
      {nil, nil} -> {:ok, nil}
      {nil, _version} -> :error
      {id, version} -> families |> Enum.find(&(&1.id == id)) |> version_of(version)
    end
  end

  defp version_of(nil, _version), do: :error

  defp version_of(family, nil),
    do:
      {:ok, %{family: family, version: nil, latest: hd(family.versions), newer: nil, older: nil}}

  defp version_of(%{versions: versions} = family, version) do
    case Enum.find_index(versions, &(&1 == version)) do
      nil ->
        :error

      index ->
        {:ok,
         %{
           family: family,
           version: version,
           latest: hd(versions),
           newer: if(index > 0, do: Enum.at(versions, index - 1)),
           older: Enum.at(versions, index + 1)
         }}
    end
  end

  @doc """
  The address of the Results page for the coordinates given. A coordinate left
  out, or given as nil, is every value of it.
  """
  def url(coordinates) do
    params =
      for key <- @coordinates,
          value = coordinates[key],
          do: {Atom.to_string(key), to_string(value)}

    case params do
      [] -> "/results"
      params -> "/results?" <> URI.encode_query(params)
    end
  end

  @doc "A harness's name as a reader reads it."
  def label("hermes-agent"), do: "Hermes"
  def label("prime-agent"), do: "Prime Agent"
  def label("codex"), do: "Codex"
  def label(id), do: id

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
