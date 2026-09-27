defmodule TechtreeWeb.ErrorMD do
  @moduledoc """
  What a request that asked for Markdown is told when it reaches no page: the
  status and the public places to go instead, without request or exception
  details.
  """

  def render(template, _assigns) do
    template
    |> Phoenix.Controller.status_message_from_template()
    |> RegentAgentAccess.Recovery.markdown(TechtreeWeb.PublicDocuments.recovery_links())
  end
end
