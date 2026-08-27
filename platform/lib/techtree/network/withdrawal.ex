defmodule Techtree.Network.Withdrawal do
  @moduledoc """
  Taking a published entry off the log by adding to the log.

  A published result is evidence somebody else may already be holding a copy
  of, and deleting the row would make this site disagree with those copies
  while claiming to be the record. So withdrawal is an event: the row here is
  the record of it, and the entry's `withdrawn_at` is written from this row
  rather than being the fact itself. The entry keeps everything it had, and
  stops appearing.

  The reason is written by whoever operates this site, from a fixed short list
  rather than free text, because this is the one place a sentence could reach a
  public surface without having been signed by anybody. Today no public surface
  shows it at all.
  """

  use Ash.Resource,
    otp_app: :techtree,
    domain: Techtree.Network,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer]

  postgres do
    table "network_withdrawals"
    repo Techtree.Repo

    references do
      reference :submission, on_delete: :nothing, on_update: :nothing
    end
  end

  actions do
    defaults [:read]

    create :record do
      description "Append one withdrawal against an entry. Ingest only."

      accept [:reason]

      argument :submission_id, :uuid, allow_nil?: false

      change manage_relationship(:submission_id, :submission, type: :append)
    end
  end

  policies do
    policy action_type(:read) do
      authorize_if always()
    end

    policy action_type([:create, :update, :destroy, :action]) do
      forbid_if always()
    end
  end

  attributes do
    uuid_primary_key :id

    attribute :reason, :atom do
      description "Why the entry was withdrawn."
      allow_nil? false
      public? true
      constraints one_of: [:requested_by_publisher, :withdrawn_by_operator]
    end

    create_timestamp :inserted_at
  end

  relationships do
    belongs_to :submission, Techtree.Network.Submission do
      description "The entry this withdrawal was appended against."
      allow_nil? false
      public? true
    end
  end
end
