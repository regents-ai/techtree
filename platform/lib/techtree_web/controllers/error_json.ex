defmodule TechtreeWeb.ErrorJSON do
  @moduledoc """
  What a request that reached no controller is told: an unknown address, a body
  that could not be read, or an unexpected failure.

  The body is `{"error": {"code", "message", "hint"}}`: a stable code derived
  from the status, the status message, and where to read what this site does
  answer. A refusal from a controller instead says whether retrying could help
  (`TechtreeWeb.ExactResponse`).
  """

  alias TechtreeWeb.Endpoint

  @doc """
  Render a status-code template as the recovery error body.
  """
  def render(template, _assigns) do
    template
    |> Phoenix.Controller.status_message_from_template()
    |> RegentAgentAccess.Recovery.json(
      "See #{Endpoint.url()}/docs and #{Endpoint.url()}/openapi.json for supported requests."
    )
  end
end
