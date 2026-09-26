defmodule TechtreeWeb.OpenAPIController do
  @moduledoc "The OpenAPI description of this site's API, as JSON."

  use TechtreeWeb, :controller

  def show(conn, _params), do: json(conn, TechtreeWeb.OpenAPI.document())
end
