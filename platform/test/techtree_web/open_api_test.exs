defmodule TechtreeWeb.OpenAPITest do
  @moduledoc """
  The OpenAPI document is one file written by hand, `priv/public/openapi.json`,
  so a route added to the router and not to the file would drift silently, and
  so would the request budget the file states. Every API route the router
  answers must be described, with an operation id, and the budget must be
  production's.
  """

  use ExUnit.Case, async: true

  alias TechtreeWeb.PublicDocuments

  test "every API route, account tool, agent request and /healthz is described with an operation id" do
    paths = PublicDocuments.openapi()["paths"]

    routes =
      for %{verb: verb, path: path, plug: plug} <- TechtreeWeb.Router.__routes__(),
          plug != RegentIdentity.HTTP,
          path == "/healthz" or
            String.starts_with?(path, ["/api/v1/", "/api/model-climb/v1/"]),
          do: {Regex.replace(~r/:(\w+)/, path, "{\\1}"), Atom.to_string(verb)}

    # The agent requests are one mount, answering three requests, and the
    # person's profile is another, answering two.
    routes =
      routes ++
        for %{plug: RegentAgents.HTTP} <- TechtreeWeb.Router.__routes__(),
            request <- [
              {"/api/agents/v1/pair", "post"},
              {"/api/agents/v1/me", "get"},
              {"/api/agents/v1/whoami", "get"}
            ],
            do: request

    routes =
      routes ++
        for %{plug: RegentIdentity.HTTP} <- TechtreeWeb.Router.__routes__(),
            request <- [{"/api/v1/profile", "get"}, {"/api/v1/profile", "patch"}],
            do: request

    for {path, verb} <- routes do
      assert %{"operationId" => id} = get_in(paths, [path, verb]),
             "#{String.upcase(verb)} #{path} is not in the OpenAPI document"

      assert is_binary(id)
    end

    ids = for {_path, operations} <- paths, {_verb, op} <- operations, do: op["operationId"]
    assert length(ids) == length(Enum.uniq(ids))
    assert length(ids) == length(routes)
  end

  test "the request budget the document states is production's" do
    [limit: limit, window_seconds: window] =
      "config/config.exs"
      |> Config.Reader.read!(env: :prod, target: :host)
      |> get_in([:techtree, :request_rate_limit])

    headers = PublicDocuments.openapi()["components"]["headers"]

    assert headers["RateLimitPolicy"]["example"] == ~s("default";q=#{limit};w=#{window})
    assert headers["RateLimit"]["example"] == ~s("default";r=#{limit - 1};t=42)
  end

  test "the document names the address it is served from" do
    document = PublicDocuments.openapi()

    assert document["servers"] == [%{"url" => TechtreeWeb.Endpoint.url()}]
    assert document["externalDocs"] == %{"url" => TechtreeWeb.Endpoint.url() <> "/docs"}
  end
end
