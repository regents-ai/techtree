defmodule Techtree.WalletBench.Turn.Changes.CorrectCheck do
  @moduledoc """
  A reviewer's correction to one of the judge's checks on a judged turn
  (`:correct_check`). Only that check's answer and reason change in the stored
  ruling; the new reason is the reviewer's, then who reviewed, then the judge's
  own reason, so what the judge said stays readable. The outcome, summary,
  reasoning, every other check, the evidence and the costs stay as they were,
  and no judge is asked.

  A check that already has the answer changes nothing, so the action's event
  (recorded only while the ruling changes) is written once however often the
  correction is run. A check the ruling does not have is refused.
  """

  use Ash.Resource.Change

  import Techtree.WalletBench.Attempt.Changes.RecordEvent, only: [put_detail: 2]

  @impl true
  def change(changeset, _opts, _context) do
    id = Ash.Changeset.get_argument(changeset, :criterion)
    value = Ash.Changeset.get_argument(changeset, :value)

    case changeset.data.judgment do
      %{"criteria" => %{^id => %{"value" => ^value}}} ->
        changeset

      %{"criteria" => %{^id => judged}} = judgment ->
        reason = Ash.Changeset.get_argument(changeset, :reason)
        reviewer = Ash.Changeset.get_argument(changeset, :reviewer)

        corrected = %{
          "value" => value,
          "reason" =>
            "#{reason} Corrected by #{reviewer}. The judge's reason: #{judged["reason"]}"
        }

        changeset
        |> Ash.Changeset.force_change_attribute(
          :judgment,
          put_in(judgment, ["criteria", id], corrected)
        )
        |> put_detail(%{
          criterion: id,
          from: judged["value"],
          to: value,
          reason: reason,
          reviewer: reviewer
        })

      _judgment ->
        Ash.Changeset.add_error(changeset,
          field: :criterion,
          message: "the turn's ruling has no check #{id}"
        )
    end
  end
end
