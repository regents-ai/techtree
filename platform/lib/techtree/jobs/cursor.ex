defmodule Techtree.Jobs.Cursor do
  @moduledoc """
  How far one staking contract's job payments have been read on one chain, at
  the latest block (`Techtree.Jobs.Scanner`): the first block not read yet, and
  the head last seen and when.

  The cursor opens at the head the first time the contract's reading job runs
  (`Techtree.Jobs.ReadPayments`), so a deposit made before then is never read.
  It moves only from where its pass found it, in the transaction that saves
  what that pass read.
  """

  use Ash.Resource,
    otp_app: :techtree,
    domain: Techtree.Jobs,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer]

  postgres do
    table "job_cursors"
    repo Techtree.Repo
  end

  actions do
    defaults [:read]

    # Opens the cursor, or leaves one already open as it stands.
    create :open do
      accept [:chain_id, :contract, :next_block]
      upsert? true
      upsert_identity :unique_cursor
      upsert_fields []
      upsert_condition expr(false)
      return_skipped_upsert? true
    end

    # Moves only a cursor still where this pass found it, so a second
    # machine's pass is never undone.
    update :advance do
      accept [:next_block, :head_block, :head_block_hash, :observed_at]
      require_attributes [:next_block, :head_block, :head_block_hash, :observed_at]
      argument :from, :integer, allow_nil?: false
      validate Techtree.Jobs.CursorUnmoved
    end
  end

  policies do
    policy action_type(:read) do
      authorize_if always()
    end

    policy action([:open, :advance]) do
      authorize_if actor_attribute_equals(:role, :system)
    end
  end

  attributes do
    uuid_primary_key :id
    attribute :chain_id, :integer, allow_nil?: false, public?: true, constraints: [min: 1]

    attribute :contract, :string,
      allow_nil?: false,
      public?: true,
      constraints: [match: ~r/\A0x[0-9a-f]{40}\z/]

    # The first block not read yet.
    attribute :next_block, :integer, allow_nil?: false, public?: true, constraints: [min: 0]
    attribute :head_block, :integer, public?: true, constraints: [min: 0]

    attribute :head_block_hash, :string,
      public?: true,
      constraints: [match: ~r/\A0x[0-9a-f]{64}\z/]

    attribute :observed_at, :utc_datetime_usec, public?: true
  end

  identities do
    identity :unique_cursor, [:chain_id, :contract]
  end
end
