defmodule Techtree.Messages.Refused do
  @moduledoc """
  A message refused with the code its caller is told, such as
  `idempotency_conflict`.
  """

  use Splode.Error, fields: [:code], class: :invalid

  def message(%{code: code}), do: "Refused: #{code}"
end
