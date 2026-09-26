defmodule TechtreeWeb.OpenAPITest do
  @moduledoc """
  The OpenAPI document is written by hand beside the router, so a route added
  to one and not the other would drift silently. Every API route the router
  answers must be described, with an operation id.
  """

  use ExUnit.Case, async: true

  test "every /api/v1 route and /healthz is described with an operation id" do
    paths = TechtreeWeb.OpenAPI.document()["paths"]

    routes =
      for %{verb: verb, path: path} <- TechtreeWeb.Router.__routes__(),
          path == "/healthz" or String.starts_with?(path, "/api/v1/"),
          do: {Regex.replace(~r/:(\w+)/, path, "{\\1}"), Atom.to_string(verb)}

    for {path, verb} <- routes do
      assert %{"operationId" => id} = get_in(paths, [path, verb]),
             "#{String.upcase(verb)} #{path} is not in the OpenAPI document"

      assert is_binary(id)
    end

    ids = for {_path, operations} <- paths, {_verb, op} <- operations, do: op["operationId"]
    assert length(ids) == length(Enum.uniq(ids))
    assert length(ids) == length(routes)
  end
end
