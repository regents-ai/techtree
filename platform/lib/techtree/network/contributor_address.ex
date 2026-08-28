defmodule Techtree.Network.ContributorAddress do
  @moduledoc """
  An Ethereum address somebody chose to leave, held apart from everything they
  published.

  This is the one thing in this application that a person typed rather than a
  machine signed, and every rule about it follows from that.

  ## It is keyed by the address, and that is the whole shape

  The founder gave this table its columns himself: the address as the primary
  key, a count of how many publications have supplied it, a pointer to the
  publication that most recently did, and the two times.

  Keying by the address is what makes the count mean anything. The same person
  publishing four runs and leaving the same address each time is one row that
  says four, not four rows nobody has to reconcile. Two people who somehow left
  the same string are the same row too, which is correct: nobody proved control
  of it either way, so there is no basis on which this table could tell them
  apart, and inventing one would be inventing a fact.

  `publication_id` is singular because the founder's word for it was singular,
  and a person may publish many runs, so it points at the publication that most
  recently supplied the address and `submission_count` carries the rest. If
  every publication were to be linked instead, that is a join table and a
  different ruling.

  It is a plain identifier and deliberately not an association. A relationship
  here would be a path something could load an address along, and the one
  property this table has to keep is that nothing outside `Techtree.Network.
  Ingest` can reach it at all. It cannot dangle: a published entry is never
  deleted, because withdrawal appends an event and no destroy action exists on
  the log to do otherwise.

  There is no `participant_key_id` column, and its absence is deliberate rather
  than an omission. The publication it points at already carries the key that
  signed it, so a copy here would be a second place holding the same fact and a
  second place to forget when somebody asks for their address back. A column
  that earns nothing and can be missed on removal is worse than no column.

  ## It is never public

  Not on the log, not on an entry's page, not in any response any address on
  this site returns, not in the submitted bytes, not in the receipt bytes, not
  in a log line, not in telemetry, not in the details of a refusal, and not in
  a URL or a query string. The log reads exactly the same whether one was left
  or not. There is no read action here that anything but `Techtree.Network.
  Ingest` can reach — every action on this resource, reads included, is
  forbidden through any interface — and there is no relationship from here to a
  publication entry, so no page and no projection could render one by following
  an association it happened to load.

  ## It is unverified, and this table claims nothing else

  A string somebody typed is not proof of control of an account. Signing for an
  account is a different and checkable thing, and when it arrives it will sit
  beside this rather than upgrade it. Every row here is unverified, without
  exception and without a column saying so, because a column that is the same
  value in every row records nothing — what records it is that this resource
  has no way to hold a verified one and no action that could mark one.

  ## Nothing is promised for it

  It is kept for the possibility of recognising contributors later. That is an
  intention, not a commitment, and no copy anywhere on this site may imply that
  leaving one earns anything.

  ## Removal means removal

  It is not part of the append-only evidence — it is a detail somebody
  volunteered about themselves — so there is a destroy action here, which there
  deliberately is not on a publication entry. Asking for it back takes the row
  away and the log is untouched by that. Because the address is the key, one
  destroy is the whole of it however many publications supplied it, which is
  the second reason this shape is the right one.

  Removal is from the active system and from any future use. It is not a claim
  of erasure from database backups: this release does not implement that and
  will not imply it.
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

    read :by_address do
      description "The one record for an address, if there is one. Ingest only."

      get? true

      argument :address, :string, allow_nil?: false

      filter expr(address == ^arg(:address))
    end

    create :record do
      description """
      Note that this address was volunteered, whether or not it has been
      before. Ingest only.
      """

      accept [:address, :publication_id]

      # Both times are read off one clock rather than two, so a row that has
      # only ever been written once says first and last were the same moment
      # instead of a few microseconds apart for no reason a reader could name.
      argument :seen_at, :utc_datetime_usec do
        allow_nil? false
        default &DateTime.utc_now/0
      end

      # One address is one row, so a second publication leaving the same
      # address is an update of the row that is already there. It is an upsert
      # rather than a look-then-write because two publications carrying the
      # same address can land at the same instant, and a read that decides
      # which of them is the first one is correct until they do.
      upsert? true
      upsert_fields [:publication_id, :last_seen_at]

      change set_attribute(:first_seen_at, arg(:seen_at))
      change set_attribute(:last_seen_at, arg(:seen_at))

      # Counted in the database, in the same statement, for the same reason.
      # `first_seen_at` is not among the upsert's fields, so it keeps the value
      # the first publication wrote.
      change atomic_update(:submission_count, expr(submission_count + 1))
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
    attribute :address, :string do
      description "The canonical lowercase `0x` form. Nobody proved control of it."
      primary_key? true
      allow_nil? false
      writable? true
      public? false
    end

    attribute :submission_count, :integer do
      description "How many publications have supplied this address."
      allow_nil? false
      default 1
      public? false
    end

    attribute :publication_id, :uuid do
      description "The publication that most recently supplied it."
      allow_nil? false
      public? false
    end

    attribute :first_seen_at, :utc_datetime_usec do
      description "When the first publication supplied it."
      allow_nil? false
      default &DateTime.utc_now/0
      public? false
    end

    attribute :last_seen_at, :utc_datetime_usec do
      description "When a publication last supplied it."
      allow_nil? false
      default &DateTime.utc_now/0
      public? false
    end
  end
end
