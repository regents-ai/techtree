defmodule Techtree.Jobs do
  @moduledoc """
  Work a signed-in agent orders from Techtree's team (`Techtree.Jobs.Order`), and
  the payments that pay for it (`Techtree.Jobs.Deposit`).

  An agent asks for a job; the team checks it and quotes it, or refuses it. A
  quote gives the order a payment reference, and the order is paid by
  depositing USDC into REGENT revenue staking on Base with that reference
  (`Techtree.Jobs.Payment`). The site never signs or sends anything: whoever pays
  signs the two calls, and the site reads the deposits from the chain
  (`Techtree.Jobs.Staking`).
  """

  use Ash.Domain, otp_app: :techtree

  resources do
    resource Techtree.Jobs.Order do
      define :request_order, action: :request, args: [:lane, :title, :success]
      define :get_order, action: :read, get_by: [:id]
      define :check_order, action: :check

      define :quote_order,
        action: :set_quote,
        args: [:quote_amount, :quote_scope, :quote_expires_at]

      define :refuse_order, action: :refuse
      define :cancel_order, action: :cancel
      define :look_now, action: :look_now
    end

    resource Techtree.Jobs.Deposit do
      define :list_deposits, action: :read
    end
  end
end
