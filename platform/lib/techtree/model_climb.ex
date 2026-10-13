defmodule Techtree.ModelClimb do
  @moduledoc """
  Model Climb on the site (contract `docs/spec/model-climb-v1.md`): the proofs
  a person's paired agents send, kept privately for that person. Training and
  evaluation run on the person's own machine and accounts; nothing here spends.
  """

  use Ash.Domain, otp_app: :techtree

  resources do
    resource Techtree.ModelClimb.Report do
      define :submit_report, action: :submit, args: [:proof, :idempotency_key]
      define :list_my_reports, action: :mine

      define :get_my_report,
        action: :mine_by_digest,
        args: [:report_digest],
        not_found_error?: false
    end
  end
end
