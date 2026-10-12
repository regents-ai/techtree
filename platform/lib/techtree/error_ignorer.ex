defmodule Techtree.ErrorIgnorer do
  @moduledoc """
  Leaves out an exception the site answers below 500, such as not found or a bad
  request. Anyone can raise those by visiting a wrong address, so saving them
  would let anyone fill the table. Server faults, exits and throws are all kept.
  """

  @behaviour ErrorTracker.Ignorer

  @impl ErrorTracker.Ignorer
  def ignore?(%ErrorTracker.Error{kind: "Elixir." <> _module = kind}, _context),
    do: kind |> String.to_existing_atom() |> visitors?()

  def ignore?(_error, _context), do: false

  # Ash's four error classes take their status from the errors they wrap, so the
  # class names whose doing it was: bad input or a refusal, or a server fault.
  defp visitors?(class) when class in [Ash.Error.Invalid, Ash.Error.Forbidden], do: true
  defp visitors?(class) when class in [Ash.Error.Unknown, Ash.Error.Framework], do: false

  defp visitors?(exception),
    do:
      Code.ensure_loaded?(exception) and function_exported?(exception, :exception, 1) and
        Plug.Exception.status(exception.__struct__()) < 500
end
