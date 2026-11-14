defmodule Techtree.Messages.Enquiry do
  @moduledoc """
  One enquiry a visitor sends from the contact form on the home page and each
  service's page (`TechtreeWeb.Components.Enquiry`): their name, work email and
  company, the service it is about and what they want to improve, and when it
  was sent. Anyone may send one, signed in or not, and nothing records who was
  signed in.

  Each client address sends a few an hour (`:enquiry_address` in
  `Techtree.Limits`, counted by `SpendAllowance`); the address itself is never
  kept. Only the site's admins read enquiries (`RegentAgents.Checks.Admin`),
  beside the team's messages (`TechtreeWeb.TeamMessagesLive`). Nothing is sent
  anywhere when one arrives.
  """

  use Ash.Resource,
    domain: Techtree.Messages,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer]

  alias Techtree.Messages.Enquiry.SpendAllowance

  @services [:skills, :evals, :environments, :models, :security]
  @shown_text "Use letters, numbers and marks you can see."
  # One @, a dot after it, and nothing spaced or hidden anywhere in it.
  @email ~r/\A[^\s@\p{Cc}\p{Cf}]+@[^\s@\p{Cc}\p{Cf}]+\.[^\s@\p{Cc}\p{Cf}]+\z/u

  postgres do
    table "enquiries"
    repo Techtree.Repo

    custom_indexes do
      index [:inserted_at, :id]
    end
  end

  actions do
    defaults [:read]

    # The team's list, newest first, a page at a time.
    read :newest do
      prepare build(sort: [inserted_at: :desc, id: :desc])
      pagination keyset?: true, default_limit: 50
    end

    create :send do
      accept [:name, :email, :company, :service, :goal]
      # A missing service gets its own words below, rather than a text field's.
      allow_nil_input [:service]
      validate present(:service), message: "Choose a service."
      validate match(:name, RegentFormat.Name.pattern()), message: @shown_text
      validate match(:company, RegentFormat.Name.pattern()), message: @shown_text
      validate match(:goal, RegentFormat.Text.pattern()), message: @shown_text
      validate match(:email, @email), message: "Use an email address, such as name@company.com."
      change SpendAllowance
    end
  end

  policies do
    # Any visitor, signed in or not.
    policy action(:send) do
      authorize_if always()
    end

    # The site's admins. Strict, so anyone else is refused, not shown an empty list.
    policy action_type(:read) do
      access_type :strict
      authorize_if RegentAgents.Checks.Admin
    end
  end

  attributes do
    uuid_primary_key :id
    attribute :name, :string, allow_nil?: false, public?: true, constraints: [max_length: 100]
    attribute :email, :string, allow_nil?: false, public?: true, constraints: [max_length: 254]
    attribute :company, :string, allow_nil?: false, public?: true, constraints: [max_length: 100]

    attribute :service, :atom,
      allow_nil?: false,
      public?: true,
      constraints: [one_of: @services]

    # What they want to improve, in their own words.
    attribute :goal, :string, allow_nil?: false, public?: true, constraints: [max_length: 2000]
    create_timestamp :inserted_at, public?: true
  end

  @doc "The services an enquiry can be about, in the order the form lists them."
  @spec services() :: [atom()]
  def services, do: @services
end
