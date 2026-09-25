defmodule TechtreeWeb.CampaignFacts do
  @moduledoc """
  The few coordinates the pages need that the catalog's display summary does
  not carry, read from the published documents themselves.

  A Climb's summary is a projection, and projections are deliberately small.
  What a reader needs beyond it — the limits on each try, the key the subject's
  model calls use, how many tasks the run covers, and what the publisher's own
  check of the tasks concluded — is written in documents this site already
  publishes under a content address. It is read from those exact bytes here
  rather than added to the summary, so a page that shows it is showing the
  document, not a copy of it that could drift.

  One field is read and never published. A Campaign's budget includes a money
  figure, and what a trial costs is set by the reader's model provider, not by
  this site. The limits this module returns are the ones a reader can act on:
  calls and tokens.

  Every limit is per try. A run tries each task without the Skill and with it,
  as many times as the Campaign's rollouts say, and a failed try may be run
  again up to the Campaign's retry limit. Each try stops starting model calls
  once it reaches any one of its limits; the call that crosses a limit still
  finishes.
  """

  alias Techtree.Catalog.Query

  @type t :: %{membership: map(), validation: map()}

  @type trial :: %{
          provider: String.t(),
          model_id: String.t(),
          credential_env: String.t(),
          tasks: pos_integer(),
          rollouts: pos_integer(),
          retries: non_neg_integer(),
          calls: pos_integer(),
          input_tokens: pos_integer(),
          output_tokens: pos_integer()
        }

  # Each task is tried without the Skill and with it.
  @sides 2

  @empty %{membership: %{}, validation: %{}}

  @doc """
  The published task membership and validation outcome behind one Climb, or
  empty values when this release publishes neither.
  """
  @spec for_climb(map() | nil) :: t()
  def for_climb(nil), do: @empty

  def for_climb(%{projection: facts}) do
    case object(facts["campaign_spec_digest"]) do
      nil ->
        @empty

      campaign ->
        %{
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
  What one Climb asks of the person running it, read from its Campaign: the
  model and provider its calls go to, the key they are charged to, how many
  tasks it runs, and the limits on each try.

  The importer refuses a Climb whose Campaign leaves any of these out, so a
  Climb without them is a broken catalog and raises here.
  """
  @spec trial!(map()) :: trial()
  def trial!(climb), do: climb |> campaign!() |> trial()

  @doc """
  The Campaign one Climb runs, decoded from the exact bytes this site serves.
  """
  @spec campaign!(map()) :: map()
  def campaign!(%{projection: %{"campaign_spec_digest" => digest}}) do
    {:ok, bytes, _entry} = Query.object_bytes(digest)
    Jason.decode!(bytes)
  end

  @doc """
  The per-try limits of a trial added up over a whole run: every try of every
  task on both sides, retries included, each at its own limits.

  These are the most a run can reach. The calls are the most it can start. The
  tokens are where every try stops starting calls, and the call that crosses a
  limit still finishes.
  """
  @spec run_total(trial()) :: %{
          tries: pos_integer(),
          calls: pos_integer(),
          input_tokens: pos_integer(),
          output_tokens: pos_integer()
        }
  def run_total(%{tasks: tasks, rollouts: rollouts, retries: retries} = trial) do
    tries = tasks * @sides * rollouts * (1 + retries)

    %{
      tries: tries,
      calls: tries * trial.calls,
      input_tokens: tries * trial.input_tokens,
      output_tokens: tries * trial.output_tokens
    }
  end

  @doc """
  A whole number written with thousands separators, as in 900,000.
  """
  @spec count(non_neg_integer()) :: String.t()
  def count(number) when is_integer(number) and number >= 0 do
    number
    |> Integer.to_string()
    |> String.reverse()
    |> String.graphemes()
    |> Enum.chunk_every(3)
    |> Enum.join(",")
    |> String.reverse()
  end

  @doc """
  Whether the published task list is fixed in advance, said plainly.
  """
  @spec membership_words(map()) :: String.t() | nil
  def membership_words(%{"mode" => "committed", "count" => count}) when is_integer(count),
    do: "#{count} tasks, fixed before either run"

  def membership_words(%{"count" => count}) when is_integer(count), do: "#{count} tasks"
  def membership_words(_membership), do: nil

  @doc """
  What a Campaign asks of the person running it. `trial!/1` reads it for a
  Climb; a page that already holds the Campaign reads it here.
  """
  @spec trial(map()) :: trial()
  def trial(%{
        "agents" => %{
          "subject" => %{
            "model" => %{
              "provider" => provider,
              "model_id" => model_id,
              "credential_env" => credential_env
            }
          }
        },
        "budgets" => %{
          "maximum_model_calls" => calls,
          "maximum_input_tokens" => input_tokens,
          "maximum_output_tokens" => output_tokens
        },
        "execution" => %{"retry_limit" => retries},
        "taskset" => %{"selection" => %{"num_tasks" => tasks, "num_rollouts" => rollouts}}
      })
      when is_binary(provider) and is_binary(model_id) and is_binary(credential_env) and
             is_integer(tasks) and is_integer(rollouts) and is_integer(retries) and
             is_integer(calls) and is_integer(input_tokens) and is_integer(output_tokens) do
    %{
      provider: provider,
      model_id: model_id,
      credential_env: credential_env,
      tasks: tasks,
      rollouts: rollouts,
      retries: retries,
      calls: calls,
      input_tokens: input_tokens,
      output_tokens: output_tokens
    }
  end

  # -- Internals ------------------------------------------------------------

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
end
