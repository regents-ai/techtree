defmodule Techtree.Projects.Project do
  @moduledoc """
  One project Techtree's team delivered to a customer's account: the package
  the work produced (`Techtree.Projects.Package`), kept whole, and what its
  pages show, read out of it once: the title, the service line, the verdict,
  the manifest and the report. The customer's name, and the name of the admin
  who delivered it and when, are kept as they were then.

  The customer reads their own projects, signed in or through the agent they
  paired; another person's project reads as not found. The site's admins read
  every project, find the customer's account (`Techtree.Projects.Customer`),
  deliver projects and withdraw them (`RegentAgents.Checks.Admin`). A package
  is delivered to a customer once; the same package again is refused while
  that delivery stands.

  Withdrawing takes the project away from the customer and removes its
  package, manifest and report, so a customer who asks for their project to be
  deleted can have it deleted. What the team's page shows of it stays: the
  title, service, verdict, size and checksum, who delivered it and withdrew
  it, and when.

  The package's bytes are read only by the two download reads; every other
  read leaves them out.
  """

  use Ash.Resource,
    domain: Techtree.Projects,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer]

  alias Techtree.Accounts.HumanAccount
  alias Techtree.Projects.Customer
  alias Techtree.Projects.Project.{Deliver, TeamMember}

  # What the customer's list and the team's list show.
  @listed [:title, :line, :verdict, :delivered_at]
  @team_listed @listed ++
                 [
                   :customer_name,
                   :delivered_by_name,
                   :withdrawn_at,
                   :withdrawn_by_name,
                   :package_sha256,
                   :package_size
                 ]
  @package [:title, :package, :package_sha256, :package_size]

  postgres do
    table "projects"
    repo Techtree.Repo

    identity_wheres_to_sql unique_standing_package: "withdrawn_at IS NULL"

    custom_indexes do
      index [:delivered_at, :id]
    end

    check_constraints do
      # A standing project has its contents; a withdrawn one has none left.
      check_constraint :withdrawn_at, "contents_until_withdrawn",
        check:
          "(withdrawn_at IS NULL) = (package IS NOT NULL AND manifest IS NOT NULL AND report_md IS NOT NULL)",
        message: "has its contents until it is withdrawn"
    end
  end

  actions do
    # The customer's projects, newest first.
    read :mine do
      filter expr(is_nil(withdrawn_at))
      prepare build(select: @listed, sort: [delivered_at: :desc, id: :desc])
    end

    # One of the customer's projects, as its page shows it.
    read :own do
      filter expr(is_nil(withdrawn_at))
    end

    read :own_package do
      filter expr(is_nil(withdrawn_at))
      prepare build(select: @package)
    end

    # Every project, newest first, a page at a time, withdrawn ones too.
    read :team do
      prepare build(select: @team_listed, sort: [delivered_at: :desc, id: :desc])
      pagination keyset?: true, default_limit: 50
    end

    read :team_package do
      filter expr(is_nil(withdrawn_at))
      prepare build(select: @package)
    end

    # Answers a `Techtree.Accounts.HumanAccount`, left unnamed here so this
    # resource doesn't need that one compiled first.
    action :find_customer, :struct do
      description "The account a wallet it signed in with, or its Privy id, names."
      allow_nil? true
      # A blank search finds no one.
      argument :customer, :string, allow_nil?: false, constraints: [allow_empty?: true]
      run fn input, _context -> Customer.find(input.arguments.customer) end
    end

    create :deliver do
      accept []
      # A wallet the customer's account signed in with, or its Privy id.
      argument :customer, :string, allow_nil?: false
      argument :package, :binary, allow_nil?: false
      change Deliver
      change {TeamMember, id: :delivered_by_id, name: :delivered_by_name}
    end

    update :withdraw do
      accept []
      require_atomic? false
      validate absent(:withdrawn_at), message: "This project was already withdrawn."
      change set_attribute(:withdrawn_at, &DateTime.utc_now/0)
      change set_attribute(:package, nil)
      change set_attribute(:manifest, nil)
      change set_attribute(:report_md, nil)
      change {TeamMember, id: :withdrawn_by_id, name: :withdrawn_by_name}
    end
  end

  policies do
    # The customer, signed in or through the agent they paired.
    policy action([:mine, :own, :own_package]) do
      authorize_if actor_attribute_equals(:role, :human)
      authorize_if actor_attribute_equals(:pairing, :active)
    end

    # Their own projects only, so another person's reads as not found.
    policy action([:mine, :own, :own_package]) do
      authorize_if expr(human_account_id == ^actor(:human_account_id))
    end

    # The site's admins. Strict, so anyone else is refused, not shown an empty list.
    policy action([:team, :team_package, :find_customer, :deliver, :withdraw]) do
      access_type :strict
      authorize_if RegentAgents.Checks.Admin
    end
  end

  attributes do
    uuid_primary_key :id
    attribute :title, :string, allow_nil?: false, public?: true, constraints: [max_length: 200]
    attribute :line, :atom, allow_nil?: false, public?: true, constraints: [one_of: [:skills]]

    attribute :verdict, :atom,
      allow_nil?: false,
      public?: true,
      constraints: [one_of: [:improved, :inconclusive, :not_improved]]

    # The checked manifest, the report and the package as uploaded, until the
    # project is withdrawn.
    attribute :manifest, :map, public?: true, sensitive?: true

    attribute :report_md, :string,
      public?: true,
      sensitive?: true,
      constraints: [trim?: false, allow_empty?: true]

    attribute :package, :binary, select_by_default?: false, sensitive?: true
    attribute :package_sha256, :string, allow_nil?: false, public?: true
    attribute :package_size, :integer, allow_nil?: false, public?: true
    # The customer's display name, or their short wallet, when it was delivered.
    attribute :customer_name, :string, allow_nil?: false, public?: true
    create_timestamp :delivered_at, public?: true
    attribute :delivered_by_name, :string, allow_nil?: false, public?: true
    attribute :withdrawn_at, :utc_datetime_usec, public?: true
    attribute :withdrawn_by_name, :string, public?: true
  end

  relationships do
    # The customer.
    belongs_to :human_account, HumanAccount do
      attribute_type :integer
      allow_nil? false
      public? true
    end

    belongs_to :delivered_by, HumanAccount do
      attribute_type :integer
      allow_nil? false
    end

    belongs_to :withdrawn_by, HumanAccount, attribute_type: :integer
  end

  identities do
    identity :unique_standing_package, [:human_account_id, :package_sha256],
      where: expr(is_nil(withdrawn_at)),
      message: "This package was already delivered to this customer."
  end
end
