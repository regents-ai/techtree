defmodule TechtreeWeb.ErrorJSONTest do
  use TechtreeWeb.ConnCase, async: true

  test "renders 404 in the shared error shape" do
    assert TechtreeWeb.ErrorJSON.render("404.json", %{}) ==
             %{
               "error" => %{
                 "code" => "not_found",
                 "message" => "Not Found",
                 "retryable" => false
               }
             }
  end

  test "renders 500 in the shared error shape" do
    assert TechtreeWeb.ErrorJSON.render("500.json", %{}) ==
             %{
               "error" => %{
                 "code" => "internal_server_error",
                 "message" => "Internal Server Error",
                 "retryable" => false
               }
             }
  end
end
