defmodule Techtree.Watchdog do
  @moduledoc """
  Watchdog on the site: a person keeps a list of their own sites and the
  addresses on them, proves they own each site, and sees each site's proof
  state. The paid testing part of Watchdog is not here; this is the safe first
  part, so the only request it ever makes about a customer's site is the
  ownership check (`Techtree.Watchdog.Ownership`).

  A person reads and changes only their own list, enforced by each resource's
  policies on `human_account_id`.
  """

  use Ash.Domain, otp_app: :techtree

  resources do
    resource Techtree.Watchdog.Host do
      define :list_my_hosts, action: :mine
      define :add_host, action: :add, args: [:origin]
      define :request_host_verification, action: :request_verification
      define :remove_host, action: :remove
    end

    resource Techtree.Watchdog.Route do
      define :list_my_routes, action: :mine
      define :add_route, action: :add, args: [:host_id]
      define :pause_route, action: :pause
      define :resume_route, action: :resume
      define :remove_route, action: :remove
    end
  end
end
