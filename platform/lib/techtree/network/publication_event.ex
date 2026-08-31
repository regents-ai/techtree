defmodule Techtree.Network.PublicationEvent do
  @moduledoc """
  What has happened to one published entry, in the order it happened.

  Two things can happen to an entry and both of them are appended rather than
  applied. It is `accepted` once, when the log takes it, and it may later be
  `withdrawn`, when the participant asks for it to be. Neither event edits the
  entry's own evidence: acceptance writes the row, and withdrawal writes a
  second event and a date on the row that says the second event exists.

  A published result is evidence somebody else may already be holding a copy
  of, so deleting the row would make this site disagree with those copies while
  claiming to be the record. The entry stays, its address stays, and the page
  says it was withdrawn and when.

  Every event carries the participant's own signature and the digest of what
  they signed, because both events are things the participant did rather than
  things this site decided. For `accepted` that is the signature over the
  bundle manifest — the participant saying this bundle is theirs. For
  `withdrawn` it is the signature over the withdrawal request, made with the
  same key. Neither can be forged by this site without the key, and neither can
  be produced by anybody else holding a copy of the bundle, because a signature
  over a digest is not a signature over another digest.

  There is no reason column and no free text of any kind. A withdrawal is a
  participant exercising a right they already have, and a sentence about why
  would be the one thing on this surface that nobody signed.
  """

  use Ash.Resource,
    otp_app: :techtree,
    domain: Techtree.Network,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer]

  postgres do
    table "network_publication_events"
    repo Techtree.Repo

    references do
      reference :publication_entry, on_delete: :nothing, on_update: :nothing
    end
  end

  actions do
    defaults [:read]

    read :for_entry do
      description "Everything appended against one entry, oldest first."

      argument :publication_entry_id, :uuid, allow_nil?: false

      filter expr(publication_entry_id == ^arg(:publication_entry_id))

      prepare build(sort: [inserted_at: :asc])
    end

    create :record do
      description "Append one event against an entry. Ingest only."

      accept [:kind, :payload_digest, :participant_signature]

      argument :publication_entry_id, :uuid, allow_nil?: false

      change manage_relationship(:publication_entry_id, :publication_entry, type: :append)
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

    attribute :kind, :atom do
      description "What happened: the log took the entry, or the participant withdrew it."
      allow_nil? false
      public? true
      constraints one_of: [:accepted, :withdrawn]
    end

    attribute :payload_digest, :string do
      description "The digest of the document the participant signed to cause this."
      allow_nil? false
      public? true
    end

    attribute :participant_signature, :string do
      description "That signature, as the document spells it."
      allow_nil? false
      public? true
    end

    create_timestamp :inserted_at
  end

  relationships do
    belongs_to :publication_entry, Techtree.Network.PublicationEntry do
      description "The entry this event was appended against."
      allow_nil? false
      public? true
    end
  end
end
