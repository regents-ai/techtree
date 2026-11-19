defmodule Techtree.WalletBench.Changes.KeepErrors do
  @moduledoc """
  Keeps a step's error whole. Ash turns an error that is not its own, such as a
  `RegentAnthropic.Error` or a `RegentSprites.Error`, into its text, and a step
  that later gives up could then no longer tell a refused judge from a lost
  machine. Each such error is added as Ash's own
  `Ash.Error.Unknown.UnknownError` with the original as its `value`, where
  `Techtree.WalletBench.Failure` reads it. Ash's own errors, an Oban snooze
  among them, are added as they are.
  """

  use Ash.Resource.Change

  alias Ash.Error.Unknown.UnknownError

  @impl true
  def change(changeset, _opts, _context), do: Ash.Changeset.handle_errors(changeset, &keep/2)

  defp keep(_changeset, error) do
    if Ash.Error.ash_error?(error),
      do: error,
      else: UnknownError.exception(error: text(error), value: error)
  end

  defp text(%{__exception__: true} = error), do: Exception.message(error)
  defp text(error), do: inspect(error)
end
