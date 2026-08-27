defmodule Techtree.Network.ContributorAddress do
  @moduledoc """
  An Ethereum address somebody chose to leave, held apart from everything they
  published.

  This is the one thing in this application that a person typed rather than a
  machine signed, and every rule about it follows from that.

  **It is never public.** Not on the log, not on an entry's page, not in any
  response any address on this site returns, not in the submitted bundle, and
  not in a URL or a query string. The log reads exactly the same whether one
  was left or not. Only `Techtree.Network.Ingest` may write here and only
  `Techtree.Network.Ingest` may read here; nothing on the public surface has a
  way to reach it.

  **It is unverified, and the record says so by what it does not claim.** A
  string somebody typed is not proof of control of an account. Signing for an
  account is a different and checkable thing, and when it arrives it will sit
  beside this rather than upgrade it.

  **Nothing is promised for it.** It is kept for the possibility of recognising
  contributors later. That is an intention, not a commitment, and no copy
  anywhere on this site may imply that leaving one earns anything.

  **Removal means removal.** It is not part of the append-only evidence — it is
  a detail somebody volunteered about themselves — so there is a destroy action
  here, which there deliberately is not on a submission. Asking for it back
  takes the row away, and the log is untouched by that.

  The address itself is the key. It is stored lowercase and canonicalised on
  the way in, so one account written three ways is one row, and `submission_id`
  points at whichever entry most recently supplied it.
  """

  use Ash.Resource,
    otp_app: :techtree,
    domain: Techtree.Network,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer]

  postgres do
    table "network_contributor_addresses"
    repo Techtree.Repo

    references do
      reference :submission, on_delete: :nothing, on_update: :nothing
    end
  end

  actions do
    defaults [:read]

    read :get_by_address do
      description "One record, by the address it is keyed on."
      get? true

      argument :address, :string, allow_nil?: false

      filter expr(address == ^arg(:address))
    end

    create :record do
      description "Note that this address was given again. Ingest only."

      accept [:address, :submission_count, :first_seen_at, :last_seen_at]

      argument :submission_id, :uuid, allow_nil?: false

      # The address is the primary key, so an upsert needs no identity named:
      # giving the same address again is by definition the same record.
      upsert? true

      upsert_fields [:submission_count, :last_seen_at, :submission_id]

      change manage_relationship(:submission_id, :submission, type: :append)
    end

    destroy :forget do
      description "Remove the address at its owner's request. Ingest only."
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
    attribute :address, :string do
      description "The canonical lowercase `0x` form, which is this record's key."
      allow_nil? false
      primary_key? true
      writable? true
      public? true
    end

    attribute :submission_count, :integer do
      description "How many published entries have supplied this address."
      allow_nil? false
      default 1
      public? true
      constraints min: 1
    end

    attribute :first_seen_at, :utc_datetime_usec do
      description "When this address was first given."
      allow_nil? false
      public? true
    end

    attribute :last_seen_at, :utc_datetime_usec do
      description "When this address was most recently given."
      allow_nil? false
      public? true
    end
  end

  relationships do
    belongs_to :submission, Techtree.Network.Submission do
      description "The entry that most recently supplied this address."
      allow_nil? false
      public? true
    end
  end
end
