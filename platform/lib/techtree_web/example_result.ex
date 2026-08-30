defmodule TechtreeWeb.ExampleResult do
  @moduledoc """
  The one published example comparison: a signed report from the founder's
  v0.1 certification, copied byte-exact from the run's proof bundle.

  Founder ruling 2026-08-26: the verified-run page shows this real result —
  exact counts included, an explicit exception to the band-only rule for this
  single curated example. Every number the page draws comes out of this file
  at render time; nothing is typed into a template. The proof it belongs to
  was verified offline (339 checks) before the file entered the repository,
  and the report carries only reward numbers, fingerprints and task hashes.

  The report names the campaign it was measured against. If this channel
  stops serving that campaign, the caller must stop drawing the numbers —
  a result for a campaign the site does not serve is not an example, it is
  a leftover.
  """

  @report_path "priv/examples/uplift-report.json"

  @type t :: %{
          file_digest: String.t(),
          run_id: String.t(),
          certified_on: String.t(),
          campaign_spec_digest: String.t(),
          tasks: non_neg_integer(),
          baseline_total: non_neg_integer(),
          candidate_total: non_neg_integer(),
          wins: non_neg_integer(),
          ties: non_neg_integer(),
          losses: non_neg_integer(),
          decision: String.t()
        }

  @spec load() :: t() | nil
  def load do
    path = Application.app_dir(:techtree, @report_path)

    with {:ok, raw} <- File.read(path),
         {:ok, %{"payload" => payload}} <- Jason.decode(raw),
         deltas when is_list(deltas) and deltas != [] <- payload["task_deltas"] do
      result = payload["primary_result"] || %{}

      %{
        file_digest: "sha256:" <> Base.encode16(:crypto.hash(:sha256, raw), case: :lower),
        run_id: payload["run_id"],
        certified_on: String.slice(payload["created_at"] || "", 0, 10),
        campaign_spec_digest: payload["campaign_spec_digest"],
        tasks: length(deltas),
        baseline_total: reward_total(deltas, "baseline_reward"),
        candidate_total: reward_total(deltas, "candidate_reward"),
        wins: result["wins"],
        ties: result["ties"],
        losses: result["losses"],
        decision: payload["decision"]
      }
    else
      _missing_or_unreadable -> nil
    end
  end

  @doc "The example is only drawable against the campaign it measured."
  @spec for_campaign(String.t() | nil) :: t() | nil
  def for_campaign(campaign_spec_digest) do
    case load() do
      %{campaign_spec_digest: ^campaign_spec_digest} = example
      when is_binary(campaign_spec_digest) ->
        example

      _other ->
        nil
    end
  end

  defp reward_total(deltas, key) do
    deltas |> Enum.map(&(&1[key] || 0)) |> Enum.sum() |> round()
  end
end
