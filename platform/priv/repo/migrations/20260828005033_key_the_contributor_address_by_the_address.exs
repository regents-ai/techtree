defmodule Techtree.Repo.Migrations.KeyTheContributorAddressByTheAddress do
  @moduledoc """
  The contributor address table takes the columns the founder gave it: the
  address itself as the primary key, a count of how many publications supplied
  it, a pointer to the publication that most recently did, and the two times.

  The table is dropped and rebuilt rather than altered. Nothing has been
  released, so there are no rows anywhere to carry across, and the new shape is
  not the old one under different names — the key changes from a row identifier
  nothing referred to, to the address itself, which is the point of the shape:
  the same address left with two runs is one row with a count of two rather
  than two rows nobody has to reconcile.

  `participant_key_id` does not come across. The publication the pointer names
  already carries the key that signed it, so a copy here would be a second
  place holding the same fact and a second place to forget when somebody asks
  for their address back.

  `publication_id` is a plain identifier and not a foreign key. A reference
  would be a path a query could follow from the log to a thing that is never
  public, and this table's whole property is that nothing outside the ingest
  reaches it. It cannot dangle either way: a published entry is never deleted,
  because withdrawal appends an event and the log offers no destroy action at
  all.
  """

  use Ecto.Migration

  def up do
    drop table(:network_contributor_addresses)

    create table(:network_contributor_addresses, primary_key: false) do
      add :address, :text, null: false, primary_key: true
      add :submission_count, :bigint, null: false, default: 1
      add :publication_id, :uuid, null: false

      add :first_seen_at, :utc_datetime_usec,
        null: false,
        default: fragment("(now() AT TIME ZONE 'utc')")

      add :last_seen_at, :utc_datetime_usec,
        null: false,
        default: fragment("(now() AT TIME ZONE 'utc')")
    end
  end

  def down do
    drop table(:network_contributor_addresses)

    # What the previous migration created, put back so that rolling back past
    # this one has something to drop. It comes back empty, which is the honest
    # outcome: the rows that were in it were dropped when this migration ran.
    create table(:network_contributor_addresses, primary_key: false) do
      add :id, :uuid, null: false, default: fragment("gen_random_uuid()"), primary_key: true
      add :participant_key_id, :text, null: false
      add :contributor_address_unverified, :text, null: false

      add :inserted_at, :utc_datetime_usec,
        null: false,
        default: fragment("(now() AT TIME ZONE 'utc')")
    end
  end
end
