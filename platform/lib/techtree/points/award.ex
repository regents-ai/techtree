defmodule Techtree.Points.Award do
  @moduledoc """
  Offers Regent Points what may earn, inside the transaction that made it, so
  something that rolls back offers nothing. Points decides whether it earns;
  while a rule is off nothing is queued.

    * A Credits purchase credited to an account, or a waiting one an account
      now holds (`credits.purchase_settled`), from `RegentCredits.Signals`.
      Credits is one Regents ledger, so every site names it "regents" and a
      purchase earns once.
  """

  use Ash.Resource,
    domain: Techtree.Points,
    authorizers: [Ash.Policy.Authorizer]

  alias Techtree.Actors.System

  actions do
    action :credits_purchase do
      argument :signal, :struct, allow_nil?: false

      run fn %{arguments: %{signal: signal}}, _context ->
        record(%{
          rule_id: "credits.purchase_settled",
          source_app: "regents",
          source_kind: "credits_purchase",
          source_event_key: signal.purchase_id
        })
      end
    end
  end

  policies do
    # Reached only through the signals above, after the action that emitted
    # them was allowed; each records as the system, never as the actor.
    policy always() do
      authorize_if always()
    end
  end

  signals_in do
    from RegentCredits.Signals do
      on :purchase_credited, :purchase_credited, action: :credits_purchase
      on :purchase_attributed, :purchase_attributed, action: :credits_purchase
    end
  end

  defp record(reference) do
    with {:ok, _event} <- RegentPoints.record_event(reference, actor: %System{}), do: :ok
  end
end
