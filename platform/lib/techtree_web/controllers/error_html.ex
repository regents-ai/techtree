defmodule TechtreeWeb.ErrorHTML do
  @moduledoc """
  This module is invoked by your endpoint in case of errors on HTML requests.

  See config/config.exs.
  """
  use TechtreeWeb, :html

  embed_templates "error_html/*"

  defp error_theme(%{theme: theme}) when theme in ["light", "dark"], do: theme

  defp error_theme(%{conn: %Plug.Conn{} = conn}) do
    case Plug.Conn.fetch_cookies(conn).req_cookies["techtree_theme"] do
      theme when theme in ["light", "dark"] -> theme
      _ -> "light"
    end
  end

  defp error_theme(_assigns), do: "light"

  @doc "Render statuses without a dedicated branded page using Phoenix's safe status text."
  def render(template, _assigns), do: Phoenix.Controller.status_message_from_template(template)
end
