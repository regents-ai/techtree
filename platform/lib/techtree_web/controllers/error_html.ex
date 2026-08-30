defmodule TechtreeWeb.ErrorHTML do
  @moduledoc """
  This module is invoked by your endpoint in case of errors on HTML requests.

  See config/config.exs.
  """
  use TechtreeWeb, :html

  embed_templates "error_html/*"

  @doc "Render statuses without a dedicated branded page using Phoenix's safe status text."
  def render(template, _assigns), do: Phoenix.Controller.status_message_from_template(template)
end
