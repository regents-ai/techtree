defmodule TechtreeWeb.FormErrors do
  @moduledoc """
  The words an Ash form shows under a field once the person has used it, and
  the same words for an API refusal: one line per rule the input broke.
  """

  import Phoenix.Component, only: [used_input?: 1]

  @spec messages(Phoenix.HTML.FormField.t()) :: [String.t()]
  def messages(field) do
    if used_input?(field), do: Enum.map(field.errors, &message/1), else: []
  end

  @doc "Each refused field of `error` and why, worded as the page's own form shows it."
  @spec details(Ash.Error.Invalid.t()) :: [%{field: atom(), message: String.t()}]
  def details(%Ash.Error.Invalid{errors: errors}) do
    errors
    |> Enum.filter(&AshPhoenix.FormData.Error.impl_for/1)
    |> Enum.flat_map(&List.wrap(AshPhoenix.FormData.Error.to_form_error(&1)))
    |> Enum.map(fn {field, message, values} ->
      %{field: field, message: message({message, values})}
    end)
  end

  # Ash's own words for a missing value or text that is too long name the rule a
  # value broke; these say what to do about it.
  defp message({"is required", _values}), do: "Fill this in."

  defp message({"length must be less than or equal to %{max}", values}),
    do: fill("Use %{max} characters or fewer.", values)

  defp message({message, values}), do: fill(message, values)

  # Only the values the words name are filled in: a rule may carry others that
  # are not text, such as the pattern of a `match` validation.
  defp fill(message, values) do
    Regex.replace(~r/%\{(\w+)\}/, message, fn placeholder, key ->
      Enum.find_value(values, placeholder, fn {name, value} ->
        to_string(name) == key && to_string(value)
      end)
    end)
  end
end
