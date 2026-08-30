defmodule TechtreeWeb.PublicationRouteContractTest do
  use TechtreeWeb.ConnCase, async: true

  test "a malformed publication fingerprint is a bad request", %{conn: conn} do
    served = get(conn, "/api/v1/publications/not-a-digest")

    assert served.status == 400

    assert %{"error" => %{"code" => "publication_digest_invalid", "retryable" => false}} =
             json_response(served, 400)
  end
end
