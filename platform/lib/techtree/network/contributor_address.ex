defmodule Techtree.Network.ContributorAddress do
  @moduledoc """
  An Ethereum address somebody chose to leave, held apart from everything they
  published.

  This is the one thing in this application that a person typed rather than a
  machine signed, and every rule about it follows from that.

  **It is never public.** Not on the log, not on an entry's page, not in any
  response any address on this site returns, not in the submitted bytes, not in
  the receipt bytes, not in a log line, not in telemetry, not in the details of
  a refusal, and not in a URL or a query string. The log reads exactly the same
  whether one was left or not. There is no read action here that anything but
  `Techtree.Network.Ingest` can reach — every action on this resource, reads
  included, is forbidden through any interface — and there is no relationship
  from here to a publication entry, so no page and no projection could render
  one by following an association it happened to load.

  **It is unverified, and the column says so in its own name.** A string
  somebody typed is not proof of control of an account. Signing for an account
  is a different and checkable thing, and when it arrives it will sit beside
  this rather than upgrade it.

  **Nothing is promised for it.** It is kept for the possibility of recognising
  contributors later. That is an intention, not a commitment, and no copy
  anywhere on this site may imply that leaving one earns anything.

  **Removal means removal from the active system and from any future use.** It
  is not part of the append-only evidence — it is a detail somebody
  volunteered about themselves — so there is a destroy action here, which there
  deliberately is not on a publication entry. Asking for it back takes the rows
  away and the log is untouched by that. It is not a claim of erasure from
  database backups: this release does not implement that and will not imply it.

  Three columns and no more: which participant key left it, the address as its
  canonical lowercase self, and when. It is keyed by the participant's key
  rather than by an entry, because what somebody volunteers is about them and
  not about one run of theirs.
  """

  use Ash.Resource,
    otp_app: :techtree,
    domain: Techtree.Network,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer]

  postgres do
    table "network_contributor_addresses"
    repo Techtree.Repo
  end

  actions do
    defaults [:read]

    read :for_address do
      description "Every record carrying one address. Ingest only."

      argument :contributor_address_unverified, :string, allow_nil?: false

      filter expr(contributor_address_unverified == ^arg(:contributor_address_unverified))
    end

    create :record do
      description "Note that this address was volunteered. Ingest only."

      accept [:participant_key_id, :contributor_address_unverified]
    end

    destroy :forget do
      description "Remove the address at its owner's request. Ingest only."
    end
  end

  policies do
    # Not even a read. Nothing on the public surface may reach this table, and
    # the way to be sure of that is for there to be no permitted action on it
    # at all — the ingest reaches it by bypassing authorization deliberately,
    # in one place a reader can find.
    policy always() do
      # Strict, so that an attempt to read this refuses out loud rather than
      # coming back empty. A silent empty list is how a table nobody may read
      # becomes a table somebody thinks they read.
      access_type :strict

      forbid_if always()
    end
  end

  attributes do
    uuid_primary_key :id

    attribute :participant_key_id, :string do
      description "The fingerprint of the key belonging to whoever left this."
      allow_nil? false
      public? false
    end

    attribute :contributor_address_unverified, :string do
      description "The canonical lowercase `0x` form. Nobody proved control of it."
      allow_nil? false
      public? false
    end

    create_timestamp :inserted_at
  end
end
