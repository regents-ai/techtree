defmodule TechtreeWeb.CampaignFacts do
  @moduledoc """
  The few coordinates the pages need that the catalog's display summary does
  not carry, read from the published documents themselves.

  A Climb's summary is a projection, and projections are deliberately small.
  Two things a reader looking at evidence needs are not in it: what the run is
  allowed to spend, and what the publisher's own check of the tasks concluded.
  Both are written in documents this site already publishes under a content
  address, so they are read from those exact bytes here rather than added to
  the summary — a page that shows them is showing the document, not a copy of
  it that could drift.

  One field is read and never published. A run's ceiling includes a money
  figure, and what a trial costs is set by the reader's model provider, not by
  this site. The ceilings this module returns are the ones a reader can act on:
  calls and tokens.
  """

  alias Techtree.Catalog.Query

  @type t :: %{
          budget: map(),
          membership: map(),
          validation: map()
        }

  @empty %{budget: %{}, membership: %{}, validation: %{}}

  @doc """
  The published budget, task membership, and validation outcome behind one
  Climb, or empty maps when this release publishes none of them.
  """
  @spec for_climb(map() | nil) :: t()
  def for_climb(nil), do: @empty

  def for_climb(%{projection: facts}) do
    case object(facts["campaign_spec_digest"]) do
      nil ->
        @empty

      campaign ->
        %{
          budget: budget(campaign),
          membership: membership(campaign),
          validation: validation(facts["validation_receipt_digest"])
        }
    end
  end

  def for_climb(_climb), do: @empty

  @doc """
  How many of the published tasks the publisher's check found valid, in words.
  """
  @spec validation_words(map()) :: String.t() | nil
  def validation_words(%{"valid" => count, "total" => count}) when is_integer(count),
    do: "#{count} tasks validated"

  def validation_words(%{"valid" => valid, "total" => total})
      when is_integer(valid) and is_integer(total),
      do: "#{valid} of #{total} tasks valid"

  def validation_words(_validation), do: nil

  @doc """
  The run ceiling, in the two units a reader can act on.
  """
  @spec budget_words(map()) :: String.t() | nil
  def budget_words(%{"maximum_model_calls" => calls} = budget) when is_integer(calls) do
    [
      "#{calls} model calls",
      token_words(budget["maximum_input_tokens"], "input tokens"),
      token_words(budget["maximum_output_tokens"], "output tokens")
    ]
    |> Enum.reject(&is_nil/1)
    |> Enum.join(" · ")
  end

  def budget_words(_budget), do: nil

  @doc """
  Whether the published task list is fixed in advance, said plainly.
  """
  @spec membership_words(map()) :: String.t() | nil
  def membership_words(%{"mode" => "committed", "count" => count}) when is_integer(count),
    do: "#{count} tasks, fixed before either Test"

  def membership_words(%{"count" => count}) when is_integer(count), do: "#{count} tasks"
  def membership_words(_membership), do: nil

  # -- Internals ------------------------------------------------------------

  defp budget(campaign) do
    campaign
    |> Map.get("budgets", %{})
    |> Map.take(["maximum_model_calls", "maximum_input_tokens", "maximum_output_tokens"])
  end

  defp membership(campaign) do
    %{
      "mode" => get_in(campaign, ["taskset", "membership", "mode"]),
      "membership_digest" => get_in(campaign, ["taskset", "membership", "membership_digest"]),
      "count" => task_count(get_in(campaign, ["taskset", "membership", "ordered_task_hashes"]))
    }
  end

  defp task_count(hashes) when is_list(hashes), do: length(hashes)
  defp task_count(_hashes), do: nil

  defp validation(digest) do
    case object(digest) do
      nil ->
        %{}

      receipt ->
        %{
          "status" => receipt["status"],
          "method" => get_in(receipt, ["method", "kind"]),
          "valid" => get_in(receipt, ["upstream_summary", "valid"]),
          "total" => get_in(receipt, ["upstream_summary", "total"])
        }
    end
  end

  defp object(digest) when is_binary(digest) do
    with {:ok, bytes, _entry} <- Query.object_bytes(digest),
         {:ok, document} when is_map(document) <- Jason.decode(bytes) do
      document
    else
      _error -> nil
    end
  end

  defp object(_digest), do: nil

  defp token_words(count, unit) when is_integer(count), do: "#{count} #{unit}"
  defp token_words(_count, _unit), do: nil
end
