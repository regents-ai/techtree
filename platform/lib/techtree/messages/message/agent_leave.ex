defmodule Techtree.Messages.Message.AgentLeave do
  @moduledoc """
  An agent's message, the same on every surface: `%{receipt: Message.receipt/1,
  replayed: boolean}`.

  The agent's `operation_id` is kept on the message it left, once for each agent
  (the `unique_agent_operation` identity). A reuse with the same topic, text and
  reply_to answers that message's receipt (`replayed: true`) and leaves
  nothing; a reuse with any other is refused as `idempotency_conflict`. Of two
  calls with one key at once, the database keeps one, and the other answers as
  a reuse. A reuse is found before the message's allowances are counted, so a
  retry never uses one.

  Every caller passes the client address as `context: %{client_key: key}`,
  which the message's allowances count (`Techtree.Messages.Message.SpendAllowance`).
  """

  use Ash.Resource.Actions.Implementation

  alias Ash.Error.Changes.InvalidAttribute
  alias Techtree.Actors.{Agent, System}
  alias Techtree.Messages
  alias Techtree.Messages.{Message, Refused}

  @impl true
  def run(%{arguments: arguments, context: %{client_key: client_key}}, _opts, %{
        actor: %Agent{} = actor
      }) do
    case left(actor, arguments.operation_id) do
      {:ok, nil} -> leave(arguments, actor, client_key)
      {:ok, message} -> reuse(message, arguments)
      {:error, error} -> {:error, error}
    end
  end

  defp leave(arguments, actor, client_key) do
    Message
    |> Ash.Changeset.for_create(:leave, Map.take(arguments, [:topic, :body, :reply_to]),
      actor: actor,
      context: %{client_key: client_key},
      private_arguments: %{operation_id: arguments.operation_id}
    )
    |> Ash.create()
    |> case do
      {:ok, message} -> {:ok, %{receipt: Message.receipt(message), replayed: false}}
      {:error, error} -> answer_kept(error, actor, arguments)
    end
  end

  # The key was kept by a call that committed between this one's read and write.
  defp answer_kept(error, actor, arguments) do
    with true <- key_kept?(error),
         {:ok, %Message{} = message} <- left(actor, arguments.operation_id) do
      reuse(message, arguments)
    else
      _another_refusal -> {:error, error}
    end
  end

  defp key_kept?(%Ash.Error.Invalid{errors: errors}) do
    Enum.any?(errors, fn
      %InvalidAttribute{field: :agent_id, private_vars: vars} -> vars[:constraint_type] == :unique
      _other -> false
    end)
  end

  defp key_kept?(_error), do: false

  defp left(actor, operation_id),
    do: Messages.get_agent_message(actor.agent_id, operation_id, actor: %System{})

  defp reuse(message, arguments) do
    if Map.take(message, [:topic, :body, :reply_to]) ==
         %{topic: arguments.topic, body: arguments.body, reply_to: arguments[:reply_to]},
       do: {:ok, %{receipt: Message.receipt(message), replayed: true}},
       else: {:error, Refused.exception(code: "idempotency_conflict")}
  end
end
