defmodule Techtree.WalletBench.VersionNote do
  @moduledoc """
  Something odd the bench saw about one release of an agent or of a wallet
  tool, in plain words, beside the run that showed it when there is one (Sean,
  14 October 2026: "for all tests, include a 'extra notes' or strange things
  for each harness or each wallet-signer, like an addendum, based on version
  number").

  A note belongs to a release: `version` is written the way the bench's results
  show that release, so a note sits beside every result of it and of no other.
  It is an addendum for the reader. No test, prompt, judge or check reads it,
  so adding one changes no result and starts no new results group.

  Nothing here is written through a public interface: an operator adds and
  withdraws notes from a console, with policies skipped.
  """

  use Ash.Resource,
    otp_app: :techtree,
    domain: Techtree.WalletBench,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer]

  alias Techtree.WalletBench.Catalog

  postgres do
    table "wallet_bench_version_notes"
    repo Techtree.Repo

    references do
      reference :attempt, on_delete: :nothing, on_update: :nothing
    end
  end

  actions do
    defaults [:read]

    read :listed do
      description "Every note, by agent or wallet, then release, oldest first."
      prepare build(sort: [kind: :asc, subject_id: :asc, version: :asc, inserted_at: :asc])
    end

    read :for_run do
      description "The notes on the agent release and the wallet release one run used."
      argument :harness_id, :string, allow_nil?: false
      argument :harness_version, :string
      argument :wallet_id, :string, allow_nil?: false
      argument :wallet_version, :string

      filter expr(
               (kind == :harness and subject_id == ^arg(:harness_id) and
                  version == ^arg(:harness_version)) or
                 (kind == :wallet and subject_id == ^arg(:wallet_id) and
                    version == ^arg(:wallet_version))
             )

      prepare build(sort: [kind: :asc, inserted_at: :asc])
    end

    create :add do
      description "Add one note to a release. Operator only."
      accept [:kind, :subject_id, :version, :text, :attempt_id]
      change {Techtree.WalletBench.Changes.Operator, attribute: :added_by}

      validate fn changeset, _context ->
        kind = Ash.Changeset.get_attribute(changeset, :kind)
        id = Ash.Changeset.get_attribute(changeset, :subject_id)

        if id in known(kind),
          do: :ok,
          else: {:error, field: :subject_id, message: "is not one of the bench's #{kind} ids"}
      end
    end

    destroy :withdraw do
      description "Take a note down. Operator only."
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
      description "`harness`: an agent. `wallet`: a wallet tool."
      allow_nil? false
      public? true
      constraints one_of: [:harness, :wallet]
    end

    attribute :subject_id, :string, allow_nil?: false, public?: true

    attribute :version, :string do
      description "The release, written as the bench's results show it."
      allow_nil? false
      public? true
      constraints max_length: 64
    end

    attribute :text, :string do
      allow_nil? false
      public? true
      constraints max_length: 600
    end

    attribute :added_by, :string do
      description "The operator who added it."
      constraints max_length: 64
    end

    create_timestamp :inserted_at
  end

  relationships do
    belongs_to :attempt, Techtree.WalletBench.Attempt do
      description "The run that showed it, when one did."
      public? true
    end
  end

  defp known(:harness), do: Catalog.harness_ids()
  defp known(:wallet), do: Catalog.wallet_ids()
  defp known(_kind), do: []
end
