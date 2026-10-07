defmodule Techtree.WalletBench do
  @moduledoc """
  AgentWalletBench: clean Fly Sprites machines on which coding-agent harnesses
  install and use wallet tools, with every step recorded.

  This first part owns the machines. A machine is requested by name, and from
  then on background jobs take it through each step in turn: create it on
  Sprites, save its disk as the baseline checkpoint, restore that checkpoint,
  note the machine's boot id, and confirm it is ready. Each step is one Oban
  job, queued in the same transaction that records the step before it, and each
  step appends a `Techtree.WalletBench.MachineEvent` in the transaction that
  changes the machine. A step that fails after its retries marks the machine
  failed; a failed readiness check marks it failed at once and is never retried
  (plan D18).

  Nothing here is written through a public interface: every write action's
  policy forbids it. Machines are requested and retired by an operator, from a
  console, with policies skipped (`request_machine/2` and `retire_machine/2`);
  the jobs write through AshOban.
  """

  use Ash.Domain, otp_app: :techtree

  resources do
    resource Techtree.WalletBench.Machine do
      define :request_machine, action: :request, args: [:name, :harness_id]
      define :get_machine, action: :read, get_by: [:id]
      define :retire_machine, action: :retire, args: [:reason]
    end

    resource Techtree.WalletBench.MachineEvent do
      define :list_machine_events, action: :for_machine, args: [:machine_id]
    end

    resource Techtree.WalletBench.Attempt do
      define :request_attempt, action: :request, args: [:harness_id, :wallet_id]
      define :get_attempt, action: :read, get_by: [:id]
      define :list_attempts, action: :recent
      define :withdraw_attempt, action: :withdraw, args: [:reason]
    end

    resource Techtree.WalletBench.Turn

    resource Techtree.WalletBench.AttemptEvent do
      define :list_attempt_events, action: :for_attempt, args: [:attempt_id]
    end
  end
end
