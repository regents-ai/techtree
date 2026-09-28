defmodule TechtreeWeb.ErrorJSONTest do
  use TechtreeWeb.ConnCase, async: true

  alias TechtreeWeb.Endpoint

  test "renders 404 as the recovery error body" do
    assert TechtreeWeb.ErrorJSON.render("404.json", %{}) ==
             %{error: %{code: "not_found", message: "Not Found", hint: hint()}}
  end

  test "renders 500 as the recovery error body" do
    assert TechtreeWeb.ErrorJSON.render("500.json", %{}) ==
             %{
               error: %{
                 code: "internal_server_error",
                 message: "Internal Server Error",
                 hint: hint()
               }
             }
  end

  defp hint,
    do: "See #{Endpoint.url()}/docs and #{Endpoint.url()}/openapi.json for supported requests."
end
