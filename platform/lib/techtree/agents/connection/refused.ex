defmodule Techtree.Agents.Connection.Refused do
  @moduledoc """
  A connected app's identity request was refused. `error` is the
  `{"code", "message", "hint"}` the site answered the signed request with, or
  the one `RegentMCPAgents` made before signing anything, such as
  `pairing_code_unknown`; `retry_after` is the site's `Retry-After`. `wait` is
  the seconds the signer or the site asked for with a 429, in
  `RegentMCPAgents.Tools.wait/1`'s words. With neither, no answer came, and the
  words are `RegentMCPAgents.Tools.refusal/0`'s.
  """
  use Splode.Error, fields: [:error, :retry_after, :wait], class: :forbidden

  def message(%{error: %{"message" => message}}), do: message

  def message(%{wait: seconds}) when is_integer(seconds),
    do: RegentMCPAgents.Tools.wait(seconds).error.hint

  def message(_error), do: "The identity request could not be completed."
end
