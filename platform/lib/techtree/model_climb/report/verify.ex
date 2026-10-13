defmodule Techtree.ModelClimb.Report.Verify do
  @moduledoc """
  Fills a submitted report from its checked proof, or refuses it with the first
  check that did not hold (`Techtree.ModelClimb.Proof`).
  """

  use Ash.Resource.Change

  alias Techtree.ModelClimb.Proof

  @impl true
  def change(changeset, _opts, _context) do
    case Proof.verify(Ash.Changeset.get_argument(changeset, :proof)) do
      {:ok, checked} ->
        Ash.Changeset.force_change_attributes(
          changeset,
          Map.take(checked, [
            :request_digest,
            :report_digest,
            :signer_key_id,
            :results,
            :paired_outcomes,
            :proof
          ])
        )

      {:error, %{check: check, message: message}} ->
        Ash.Changeset.add_error(
          changeset,
          Ash.Error.Changes.InvalidAttribute.exception(
            field: :proof,
            message: message,
            vars: [check: check]
          )
        )
    end
  end
end
