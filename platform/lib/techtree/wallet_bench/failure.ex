defmodule Techtree.WalletBench.Failure do
  @moduledoc """
  Why a step gave up, in plain words for the public pages, with the error's own
  text kept for operators.

  `give_up/1` runs in every action a trigger's `on_error` names. The record's
  state names the step that ran out of retries, since each trigger runs from
  its own states. The error says why when the bench knows its kind: the judge's
  model provider or the test machine provider refusing the bench's access,
  turning it away, being unavailable or out of reach. Ash keeps those errors
  whole (`Techtree.WalletBench.Changes.KeepErrors`). Anything else is a problem
  on the bench's side. A reason the bench wrote itself, given as text, is kept
  as written.

  The error's own text, blanked of secrets (`Techtree.WalletBench.Blank`), goes
  to the log as one line and never to a page.
  """

  require Logger

  alias Ash.Error.Unknown.UnknownError
  alias Techtree.WalletBench.{Attempt, Blank, Machine, Turn}

  @limit 2000

  @doc """
  The public reason for the give-up the changeset records, from its `:error`
  argument; an error that is not text is first logged for operators.
  """
  @spec give_up(Ash.Changeset.t()) :: String.t()
  def give_up(%Ash.Changeset{resource: resource, data: record} = changeset) do
    case Ash.Changeset.get_argument(changeset, :error) do
      reason when is_binary(reason) ->
        blank(reason)

      error ->
        Logger.warning(
          "Wallet Bench step gave up: resource=#{inspect(resource)} id=#{record.id} " <>
            "state=#{record.state} error=#{inspect(detail(error))}"
        )

        "#{cause(error)}, so #{outcome(resource, record.state)}."
    end
  end

  defp cause(error),
    do:
      error
      |> causes()
      |> Enum.find_value("The bench ran into a problem of its own", &said/1)

  # The errors an Ash error holds, each one kept whole as itself.
  defp causes(%UnknownError{value: value}) when not is_nil(value), do: [value]
  defp causes(%{errors: errors}) when is_list(errors), do: Enum.flat_map(errors, &causes/1)
  defp causes(error), do: [error]

  defp said(%RegentAnthropic.Error{reason: reason}),
    do: provider("The judge's model provider", answer(reason))

  defp said(%RegentSprites.Error{reason: reason}),
    do: provider("The test machine provider", answer(reason))

  defp said(%Req.TransportError{}), do: "A service the bench relies on could not be reached"
  defp said(_error), do: nil

  defp answer({:anthropic, status, _type, _message}), do: status(status)
  defp answer({:sprites, status, _message}), do: status(status)
  defp answer({:transport, _message}), do: :unreachable
  defp answer(:api_key_missing), do: :not_set_up
  defp answer(:token_missing), do: :not_set_up
  defp answer({:unpriced_model, _model}), do: :not_set_up
  defp answer(_reason), do: :unusable

  defp status(status) when status in [401, 403], do: :refused
  defp status(429), do: :busy
  defp status(status) when status >= 500, do: :unavailable
  defp status(_status), do: :turned_down

  defp provider(who, :refused), do: who <> " refused the bench's access"
  defp provider(who, :busy), do: who <> " turned the bench away for sending too many requests"
  defp provider(who, :unavailable), do: who <> " was unavailable"
  defp provider(who, :unreachable), do: who <> " could not be reached"
  defp provider(who, :not_set_up), do: who <> " is not set up for the bench"
  defp provider(who, :turned_down), do: who <> " turned down the bench's request"
  defp provider(who, :unusable), do: who <> " gave an answer the bench could not use"

  defp outcome(Turn, :queued), do: "this test did not start"
  defp outcome(Turn, :running), do: "this test's results could not be collected"
  defp outcome(Turn, :finished), do: "this test was not judged"
  defp outcome(Attempt, :requested), do: "no test machine could be taken for this run"
  defp outcome(Attempt, :leased), do: "the tests did not start"
  defp outcome(Attempt, :funding), do: "the funding could not be signed and nothing was sent"

  defp outcome(Attempt, :sending),
    do:
      "the funding sends' receipts could not be read; their outcome is unknown, and funding is paused"

  defp outcome(Attempt, :revoking),
    do: "the model key could not be confirmed removed, and the machine is being deleted"

  defp outcome(Machine, :requested), do: "the test machine could not be created"
  defp outcome(Machine, :created), do: "the test machine's setup did not finish"
  defp outcome(Machine, :built), do: "the test machine's setup could not be saved"

  defp outcome(Machine, state) when state in [:checkpointed, :resetting],
    do: "the test machine could not be put back to its saved setup"

  defp outcome(Machine, :restored), do: "the test machine's restart could not be checked"
  defp outcome(Machine, :settling), do: "the test machine could not be confirmed ready"
  defp outcome(Machine, :retiring), do: "the test machine could not be deleted"

  defp detail(error), do: error |> causes() |> Enum.map_join("; ", &text/1) |> blank()

  defp text(%{__exception__: true} = error),
    do: inspect(error.__struct__) <> ": " <> Exception.message(error)

  defp text(error), do: inspect(error)

  defp blank(text), do: text |> Blank.blank(Blank.site_known()) |> String.slice(0, @limit)
end
