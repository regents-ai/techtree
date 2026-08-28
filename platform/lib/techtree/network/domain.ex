defmodule Techtree.Network do
  @moduledoc """
  The public run log: what participants have published, and what was checked
  before it was published.

  This is kept apart from `Techtree.Catalog` because the two answer to opposite
  rules. The catalog is what this project publishes about itself, imported from
  a bundle it generated, and it is rewritten wholesale by a release. The log is
  what other people published, arriving one row at a time from outside, and
  once a row is in it, it is in it: an entry is withdrawn by appending an
  event, never by deleting the row.  Two concerns with different lifetimes,
  different writers and different failure modes do not belong in one domain.

  The write policy is the same as the catalog's, for the same reason. Every
  resource here forbids create, update and destroy through any interface, and
  exactly one module — `Techtree.Network.Ingest` — writes, with authorization
  explicitly bypassed and only after every check in
  `Techtree.Network.Bundle` has passed. That is what makes "the site verified
  this" a property of the code rather than of somebody's care.

  One resource in here is not part of the log at all.
  `Techtree.Network.ContributorAddress` holds something a person volunteered
  about themselves rather than something their machine signed, so it is not
  evidence, it is never public, and it can be removed on request. It is stored
  here because the ingest is what receives it, and nothing else in this
  application may read it — that resource forbids reads as well as writes. It
  is keyed by the address itself, so one address is one row however many
  publications supplied it, and asking for it back is one removal.
  """

  use Ash.Domain, otp_app: :techtree

  @default_rate_limit [limit: 10, window_seconds: 60]

  @default_page_size 25
  @maximum_page_size 100

  resources do
    resource Techtree.Network.PublicationEntry do
      define :list_publication_entries, action: :read
      define :get_publication_entry_by_digest, action: :get_by_digest, args: [:bundle_digest]

      define :get_publication_entry_by_run,
        action: :get_by_run,
        args: [:participant_key_id, :run_id]

      define :record_publication_entry, action: :record
      define :mark_publication_entry_withdrawn, action: :mark_withdrawn
    end

    resource Techtree.Network.PublicationEvent do
      define :list_publication_events, action: :read
      define :list_events_for_entry, action: :for_entry, args: [:publication_entry_id]
      define :record_publication_event, action: :record
    end

    resource Techtree.Network.ContributorAddress do
      define :list_contributor_addresses, action: :read
      define :get_contributor_address, action: :by_address, args: [:address]
      define :record_contributor_address, action: :record
      define :forget_contributor_address, action: :forget
    end
  end

  @doc """
  The largest submission this site will read, in bytes.

  A proof bundle is a few hundred kilobytes of digests and scores with no
  transcripts in it, and the founder fixed the cap at two mebibytes — generous
  by a factor of six, and small enough that a body over it is refused before it
  is parsed. There is no default here: the number is configuration, it is set
  in one place, and a build that lost it should say so rather than quietly pick
  a different one.
  """
  @spec maximum_body_bytes() :: pos_integer()
  def maximum_body_bytes do
    :techtree
    |> Application.fetch_env!(__MODULE__)
    |> Keyword.fetch!(:maximum_body_bytes)
  end

  @doc """
  How many submissions one address may make, and over what window in seconds.
  """
  @spec rate_limit() :: keyword()
  def rate_limit do
    :techtree
    |> Application.get_env(__MODULE__, [])
    |> Keyword.get(:rate_limit, @default_rate_limit)
  end

  @doc """
  How many entries one page of the log holds when the caller does not say.
  """
  @spec default_page_size() :: pos_integer()
  def default_page_size, do: @default_page_size

  @doc """
  The most entries one page of the log will ever hold.
  """
  @spec maximum_page_size() :: pos_integer()
  def maximum_page_size, do: @maximum_page_size
end
