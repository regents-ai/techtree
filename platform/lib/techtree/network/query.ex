defmodule Techtree.Network.Query do
  @moduledoc """
  Everything the public surface is allowed to ask about the run log.

  The pages and the read endpoints call this module and nothing else, the way
  they call `Techtree.Catalog.Query` for the catalog. Three rules live here so
  that they cannot be forgotten anywhere else.

  *The log is ordered by arrival.* Newest first, by the log sequence the
  database handed out, and by nothing else. There is no order by score, no
  rank, and no argument for one available to a caller — the Climb's own
  manifest says there is no leaderboard, and an ordering is a ranking whatever
  it is called. The words are **log sequence**: never position, never rank,
  never top.

  *A page is a keyset page.* A caller asks for everything before a sequence
  they already hold, and gets at most a hundred. Counting offsets would let a
  caller page through a log that is being appended to and see an entry twice or
  not at all; asking for what came before a sequence they are holding cannot.

  *A withdrawn entry is still on the log.* It keeps its sequence, it keeps its
  address, and it is marked withdrawn wherever it appears. Withdrawal is an
  appended event, and a log that quietly dropped the withdrawn entries would be
  a log with holes in it that nothing explained.

  Nothing in this module can see a contributor address. There is no read for
  one anywhere in this application outside `Techtree.Network.Ingest`, so no
  page could render one by accident.
  """

  require Ash.Query

  alias Techtree.Network
  alias Techtree.Network.PublicationEntry
  alias Techtree.Network.AgentVersions

  @typedoc """
  One page of the log, and where the next one starts.
  """
  @type page :: %{entries: [PublicationEntry.t()], next_before_sequence: pos_integer() | nil}

  @doc """
  One page of the log, newest arrival first.

  `:before_sequence` asks for what came before a sequence the caller already
  holds, and `:limit` for how many, capped at a hundred.
  """
  @spec page(keyword()) :: page()
  def page(options \\ []) do
    limit = Keyword.get(options, :limit, Network.default_page_size())
    before = Keyword.get(options, :before_sequence)

    # One more than asked for, which is how a keyset page knows whether there
    # is another one without counting the whole log.
    found =
      PublicationEntry
      |> Ash.Query.for_read(:list_log, %{
        before_sequence: before,
        agent: Keyword.get(options, :agent),
        agent_version: Keyword.get(options, :agent_version),
        model: Keyword.get(options, :model),
        challenge: Keyword.get(options, :challenge)
      })
      |> Ash.Query.limit(limit + 1)
      |> Ash.read!()

    entries = Enum.take(found, limit)

    next =
      if length(found) > limit do
        entries |> List.last() |> Map.fetch!(:log_sequence)
      end

    %{entries: entries, next_before_sequence: next}
  end

  @doc "Submitted agent versions, discovered independently of result pagination."
  def agent_families do
    PublicationEntry
    |> Ash.Query.for_read(:agent_versions)
    |> Ash.Query.distinct([:subject_harness, :subject_harness_version])
    |> Ash.Query.distinct_sort(log_sequence: :asc)
    |> Ash.read!()
    |> AgentVersions.families()
  end

  @doc "Model choices for one submitted harness version, independent of pagination."
  def result_models(agent, version) do
    PublicationEntry
    |> Ash.Query.for_read(:list_log, %{agent: agent, agent_version: version})
    |> Ash.Query.select([:subject_model, :log_sequence])
    |> Ash.Query.distinct(:subject_model)
    |> Ash.Query.distinct_sort(log_sequence: :desc)
    |> Ash.read!()
    |> Enum.map(& &1.subject_model)
  end

  @doc "Exact Campaign choices for one harness version and model; never merge by title."
  def result_challenges(agent, version, model) do
    PublicationEntry
    |> Ash.Query.for_read(:list_log, %{agent: agent, agent_version: version, model: model})
    |> Ash.Query.select([:campaign_spec_digest, :campaign_name, :climb_reference, :log_sequence])
    |> Ash.Query.distinct(:campaign_spec_digest)
    |> Ash.Query.distinct_sort(log_sequence: :desc)
    |> Ash.read!()
    |> Enum.map(&Map.take(&1, [:campaign_spec_digest, :campaign_name, :climb_reference]))
  end

  @doc """
  One entry by the digest of the bundle it published, withdrawn or not.
  """
  @spec get_entry(String.t()) :: {:ok, PublicationEntry.t()} | :error
  def get_entry(digest) when is_binary(digest) do
    case Network.get_publication_entry_by_digest(digest) do
      {:ok, %PublicationEntry{} = entry} -> {:ok, entry}
      _other -> :error
    end
  end

  @doc """
  The most recent published proofs for one Campaign, newest arrival first.

  This is deliberately one filtered and bounded Ash read with a narrow
  selection: the evidence graph needs only the receipt links and their
  recomputed outcome counts, not the full publication resource. The extra row
  tells the caller whether the displayed sample was capped.
  """
  @spec for_campaign(String.t()) :: %{entries: [PublicationEntry.t()], truncated?: boolean()}
  def for_campaign(campaign_spec_digest) when is_binary(campaign_spec_digest) do
    found = Network.list_publication_entries_for_campaign!(campaign_spec_digest)
    %{entries: Enum.take(found, 12), truncated?: length(found) > 12}
  end

  @doc """
  Whether an entry has been withdrawn.
  """
  @spec withdrawn?(PublicationEntry.t()) :: boolean()
  def withdrawn?(%PublicationEntry{withdrawn_at: withdrawn_at}), do: not is_nil(withdrawn_at)

  @doc """
  The keyset arguments a caller sent, or why they are not arguments.
  """
  @spec read_page_options(map()) :: {:ok, keyword()} | {:error, String.t()}
  def read_page_options(params) when is_map(params) do
    with {:ok, before} <- sequence(Map.get(params, "before_sequence")),
         {:ok, limit} <- limit(Map.get(params, "limit")),
         {:ok, selection} <- agent_options(params),
         {:ok, model} <- coordinate(Map.get(params, "model"), "model"),
         {:ok, challenge} <- coordinate(Map.get(params, "challenge"), "challenge") do
      {:ok,
       [before_sequence: before, limit: limit, model: model, challenge: challenge] ++ selection}
    end
  end

  defp agent_options(params) do
    case {Map.get(params, "agent"), Map.get(params, "agent_version")} do
      {nil, nil} ->
        {:ok, []}

      {agent, version}
      when is_binary(agent) and is_binary(version) and byte_size(agent) in 1..128 and
             byte_size(version) in 1..128 ->
        if String.trim(agent) != "" and String.trim(version) != "" do
          {:ok, [agent: agent, agent_version: version]}
        else
          {:error, "agent and agent_version must both be nonempty version coordinates"}
        end

      _ ->
        {:error, "agent and agent_version must both be nonempty version coordinates"}
    end
  end

  defp coordinate(nil, _name), do: {:ok, nil}

  defp coordinate(value, name) when is_binary(value) and byte_size(value) in 1..512 do
    if String.trim(value) == "",
      do: {:error, "#{name} must be a nonempty Result coordinate"},
      else: {:ok, value}
  end

  defp coordinate(_value, name), do: {:error, "#{name} must be a nonempty Result coordinate"}

  defp sequence(nil), do: {:ok, nil}

  defp sequence(value) when is_binary(value) do
    case Integer.parse(value) do
      {number, ""} when number > 0 -> {:ok, number}
      _other -> {:error, "before_sequence is a log sequence from an entry you already hold"}
    end
  end

  defp sequence(_value),
    do: {:error, "before_sequence is a log sequence from an entry you already hold"}

  defp limit(nil), do: {:ok, Network.default_page_size()}

  defp limit(value) when is_binary(value) do
    maximum = Network.maximum_page_size()

    case Integer.parse(value) do
      {number, ""} when number > 0 and number <= maximum -> {:ok, number}
      _other -> {:error, "limit is a whole number of entries, at most #{maximum}"}
    end
  end

  defp limit(_value), do: {:error, "limit is a whole number of entries"}
end
