defmodule TechtreeWeb.RedirectControllerTest do
  @moduledoc """
  Each retired address sends a visitor on for good (301) to the page that took
  its place, and that page is there.
  """

  use TechtreeWeb.ConnCase, async: false

  for {from, to} <- [
        {"/start", "/docs/run-locally"},
        {"/verify", "/docs/verify"},
        {"/docs/method", "/docs/verify"},
        {"/repo2rlenv", "/services/environments"},
        {"/train", "/services/models"},
        {"/services/verify", "/services/evals"},
        {"/services/verify/sample-report", "/services/evals"},
        {"/services/cyber-assist", "/services/security"},
        {"/services/cyber-assist/sample-report", "/services/security/sample-report"},
        {"/services/watchdog", "/services/security"}
      ] do
    test "#{from} moved for good to #{to}", %{conn: conn} do
      moved = get(conn, unquote(from))

      assert moved.status == 301
      assert redirected_to(moved, 301) == unquote(to)
      assert conn |> recycle() |> get(unquote(to)) |> html_response(200)
    end
  end
end
