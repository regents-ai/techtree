defmodule TechtreeWeb.ToolErrorsTest do
  # A connected app told to wait reads `retry_after` as whole seconds, whether
  # the signer or the site asked it to wait.
  use ExUnit.Case, async: true

  alias Techtree.Agents.Connection.Refused

  @site %{"code" => "too_many_requests", "message" => "Too Many Requests", "hint" => "Wait."}

  defp error(refused),
    do: refused |> AshAi.ToToolError.to_tool_error() |> Jason.decode!() |> Map.fetch!("error")

  test "every wait an identity tool reports is whole seconds" do
    assert %{"code" => "too_many_requests", "retry_after" => 45} =
             error(Refused.exception(wait: 45))

    assert %{"code" => "too_many_requests", "retry_after" => 0} =
             error(Refused.exception(error: @site, retry_after: "0"))

    refute Map.has_key?(
             error(Refused.exception(error: @site, retry_after: "soon")),
             "retry_after"
           )
  end
end
