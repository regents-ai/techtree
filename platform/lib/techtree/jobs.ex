defmodule Techtree.Jobs do
  @moduledoc """
  Work a signed-in agent orders from Techtree's team (`Techtree.Jobs.Order`), and
  the payments that pay for it (`Techtree.Jobs.Deposit`).

  An agent asks for a job; the team checks it and quotes it, or refuses it. A
  quote gives the order a payment reference, and the order is paid by
  depositing USDC into REGENT revenue staking on Base with that reference
  (`Techtree.Jobs.Payment`). The site never signs or sends anything: whoever pays
  signs the two calls, and the site's payment reader saves every job payment
  the staking contract receives and settles the orders they pay
  (`Techtree.Jobs.Reader`, run by `Techtree.Jobs.ReadPayments`, read up to
  `Techtree.Jobs.Cursor`).
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
      define :due_orders, action: :due, args: [:references, :passed_at]
      define :settle_order, action: :settle, args: [:passed_at]
    end

    resource Techtree.Jobs.Deposit do
      define :list_deposits, action: :read
      define :record_deposit, action: :record

      define :seen_deposits,
        action: :seen,
        args: [:chain_id, :contract, :from, :to, :transactions]
    end

    resource Techtree.Jobs.Cursor do
      define :get_cursor,
        action: :read,
        get_by: [:chain_id, :contract],
        not_found_error?: false

      define :open_cursor, action: :open
      define :advance_cursor, action: :advance
    end
  end
end
