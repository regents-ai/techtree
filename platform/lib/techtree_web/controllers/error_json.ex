defmodule TechtreeWeb.ErrorJSON do
  @moduledoc """
  What a request that reached no controller is told.

  The shape is the one every other refusal uses — a stable code, a safe message,
  and whether retrying could help — so that a caller has one error format to
  read rather than two. A route that does not exist says exactly that.
  """

  @doc """
  Render a status-code template as the shared error envelope.
  """
  def render(template, _assigns) do
    message = Phoenix.Controller.status_message_from_template(template)

    %{
      "error" => %{
        "code" => code(message),
        "message" => message,
        "retryable" => false
      }
    }
  end

  defp code(message) do
    message
    |> String.downcase()
    |> String.replace(~r/[^a-z0-9]+/, "_")
    |> String.trim("_")
  end
end
