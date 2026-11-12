defmodule TechtreeWeb.ToolErrors do
  @moduledoc """
  What a hosted MCP tool says when its action refuses, as the tool error's text
  (`AshAi.ToToolError`), in the site's one shape,
  `{"error": {"code", "message", "hint"}}`. A connected app's identity refusal
  takes the site's own code and words, the library's `too_many_requests` with
  `retry_after` when it was asked to wait, or, when no answer came, the words
  every Regent site gives it.

  Input a tool's action cannot take is refused before AshAi runs it
  (`check_input/3`, the server's `tool_argument_transformer`): a pairing's
  `invalid_request` in the library's words
  (`RegentMCPAgents.pairing_input_refusal/0`), and another identity tool's
  `identity_request_refused`. As AshAi reads it, a call without `input` sends
  none, which is how a tool listed with no inputs is called.
  """

  @doc """
  Casts a hosted tool's `input` as its action takes it. Input it takes goes on to
  AshAi unchanged; any other is refused as `{:error, text}`.
  """
  @spec check_input(AshAi.Tool.t(), term(), map()) :: {:ok, term()} | {:error, String.t()}
  def check_input(%AshAi.Tool{resource: resource, action: %{name: action}}, arguments, _context) do
    with %{} <- arguments,
         %{} = input <- arguments["input"] || %{},
         %{valid?: true} <- Ash.ActionInput.for_action(resource, action, input) do
      {:ok, arguments}
    else
      _refused -> {:error, refused(action)}
    end
  end

  defp refused(:pair_identity),
    do: Jason.encode!(%{error: RegentMCPAgents.pairing_input_refusal()})

  defp refused(_identity), do: Jason.encode!(RegentMCPAgents.Tools.refusal())
end

defimpl AshAi.ToToolError, for: Techtree.Agents.Connection.Refused do
  def to_tool_error(%{error: %{} = error, retry_after: retry_after}),
    do: Jason.encode!(%{error: with_retry(error, retry_after)})

  def to_tool_error(%{wait: seconds}) when is_integer(seconds) do
    %{error: error} = RegentMCPAgents.Tools.wait(seconds)
    Jason.encode!(%{error: Map.put(error, :retry_after, seconds)})
  end

  def to_tool_error(_no_answer), do: Jason.encode!(RegentMCPAgents.Tools.refusal())

  defp with_retry(error, retry_after) when is_binary(retry_after) do
    case Integer.parse(retry_after) do
      {seconds, ""} -> Map.put(error, "retry_after", seconds)
      _not_seconds -> error
    end
  end

  defp with_retry(error, _none), do: error
end
