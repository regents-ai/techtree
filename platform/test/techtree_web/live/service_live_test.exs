defmodule TechtreeWeb.ServiceLiveTest do
  @moduledoc """
  The service pages, each built from its entry in `TechtreeWeb.Services`:
  Skills, Evals, Environments and Models with their numbered steps (each step
  that runs something marked with its status), what the customer receives,
  the open-source tools grouped by status (by their own links), the shared
  terms, the price level and booking, and Models with its comparisons;
  Security with its two options, its rules and the Agent Message button. Each
  page's Markdown says the same.

  The pages are read as they render: they read the sign-in from the socket's
  connect info, which the LiveView test harness does not carry. The connected
  Agent Message window is exercised in the browser tests
  (`assets/test/browser/agent_message.spec.ts`).
  """

  use TechtreeWeb.ConnCase, async: false

  alias TechtreeWeb.Components.AgentMessage
  alias TechtreeWeb.Services

  @booking "https://calendar.example/techtree"

  # Each page's tools by their own links, Tested before Planned.
  @projects %{
    skills: [
      "https://github.com/NVIDIA/SkillEvaluator",
      "https://github.com/microsoft/SkillOpt",
      "https://github.com/PrimeIntellect-ai/verifiers"
    ],
    evals: [
      "https://github.com/PrimeIntellect-ai/verifiers",
      "https://github.com/harbor-framework/harbor",
      "https://github.com/PrimeIntellect-ai/prime-rl"
    ],
    environments: [
      "https://github.com/harbor-framework/harbor",
      "https://github.com/PrimeIntellect-ai/verifiers",
      "https://github.com/NVlabs/Skill2Env",
      "https://github.com/huggingface/Repo2RLEnv"
    ],
    models: [
      "https://github.com/PrimeIntellect-ai/verifiers",
      "https://github.com/PrimeIntellect-ai/prime-rl",
      "https://github.com/NVIDIA/NemoClaw"
    ]
  }

  # The parts each page has between what you receive and the contact band.
  @parts %{
    skills: ~w(tools terms notes),
    evals: ~w(tools terms notes),
    environments: ~w(tools terms notes),
    models: ~w(comparisons tools terms notes)
  }

  @statuses ~w(delivered tested planned)

  test "each service page has its steps in order, what you receive, its parts and booking",
       %{conn: conn} do
    for service <- Services.all() do
      page = page(conn, Services.path(service.id))

      assert ids(page, "main > section") ==
               ["opening", "process", "receive"] ++ @parts[service.id] ++ ["contact"]

      assert ids(page, "#steps > li") ==
               for(index <- 1..length(service.steps), do: "step-#{index}")

      assert texts(page, "#steps h3") == Enum.map(service.steps, & &1.name)

      # Each step's words read as written, a link run against what follows it.
      assert texts(page, "#steps .mk-steps__words") ==
               for(step <- service.steps, do: Enum.map_join(step.words, &plain/1))

      assert texts(page, "#receive li") == service.receive
      assert text(page, "h1") == service.name
      assert texts(page, "#terms li") == Services.terms()
    end
  end

  test "each service page names the tools it uses by their own links, and its steps agree",
       %{conn: conn} do
    for service <- Services.all() do
      page = page(conn, Services.path(service.id))
      tools = @projects[service.id]

      assert hrefs(page, "#tools dt a") == tools, "#{service.name}'s tools"
      assert Enum.all?(hrefs(page, "#steps a"), &(&1 in tools)), "#{service.name}'s steps"
      assert markdown(conn, Services.path(service.id)) =~ "## Tools"
    end
  end

  test "each step that runs something shows its status, and the tools sit under theirs",
       %{conn: conn} do
    for service <- Services.all() do
      path = Services.path(service.id)
      page = page(conn, path)
      markdown = markdown(conn, path)

      markers =
        for step <- LazyHTML.query(page, "#steps > li") do
          for marker <- LazyHTML.query(step, ".mk-steps__head [data-status]"),
              do: attribute(marker, "data-status")
        end

      assert markers ==
               for(step <- service.steps, do: if(step.status, do: ["#{step.status}"], else: []))

      for {step, index} <- Enum.with_index(service.steps, 1), step.status do
        assert markdown =~
                 "#{index}. **#{step.name}** (#{Services.status_name(step.status)}):"
      end

      status_of = Map.new(service.tools, &{&1.href, "#{&1.status}"})

      groups =
        for group <- LazyHTML.query(page, "#tools .mk-tools__groups > section") do
          status = String.replace_prefix(attribute(group, "id"), "tools-", "")
          links = hrefs(group, "dt a")

          assert links != [], "#{service.name} shows an empty #{status} group"
          assert Enum.all?(links, &(status_of[&1] == status))

          assert [^status] =
                   for(
                     marker <- LazyHTML.query(group, "h3 [data-status]"),
                     do: attribute(marker, "data-status")
                   )

          assert markdown =~ "### #{Services.status_name(String.to_existing_atom(status))}"
          status
        end

      assert groups == Enum.filter(@statuses, &(&1 in groups))
    end
  end

  test "each service page shows its price level beside booking, and its Markdown says it in words",
       %{conn: conn} do
    for service <- Services.all() do
      path = Services.path(service.id)
      page = page(conn, path)

      assert [price] =
               Enum.to_list(LazyHTML.query(page, ~s|#opening #price[role="img"]|))

      assert attribute(price, "aria-label") == "Price level #{service.price} of 4"

      assert length(Enum.to_list(LazyHTML.query(page, "#price .mk-price__mark--on"))) ==
               service.price

      assert has?(page, ~s|#price .mk-price__marks[aria-hidden="true"]|)

      assert markdown(conn, path) =~ "Price level: #{service.price} of 4."
    end

    page = page(conn, ~p"/services/security")
    refute has?(page, ".mk-price")
    refute markdown(conn, ~p"/services/security") =~ "Price level"
  end

  test "no service page, its search-engine data or its Markdown shows a figure for money",
       %{conn: conn} do
    money = ~r/[$£€]\s?\d|priceCurrency|"price":/

    for path <- [~p"/" | paths()] do
      refute conn |> get(path) |> html_response(200) =~ money
      refute markdown(conn, path) =~ money
    end
  end

  test "Security offers a review and monitoring, with its rules, its sample report and Your sites",
       %{conn: conn} do
    security = Services.security()
    page = page(conn, ~p"/services/security")

    assert ids(page, "#options-list > section") == Enum.map(security.options, & &1.id)

    assert hrefs(page, "#options-list .text-link") == [
             "/services/security/sample-report",
             "/watchdog"
           ]

    assert texts(page, "#rules li") == security.rules
    assert has?(page, "#contact #security-message-button")
    assert has?(page, "#security-message[data-agent-message]")

    assert markdown(conn, ~p"/services/security") =~ AgentMessage.markdown("watchdog")
    assert conn |> get(~p"/services/security/sample-report") |> html_response(200)
  end

  test "each page and its Markdown start the same email, named for the service", %{conn: conn} do
    for service <- Services.all() ++ [Services.security()] do
      path = Services.path(service.id)
      [mailto] = hrefs(page(conn, path), ~s|#contact a[href^="mailto:"]|)

      assert %URI{path: "build@regents.sh", query: query} = URI.parse(mailto)
      assert %{"subject" => subject} = URI.decode_query(query)
      assert subject == service.name
      assert markdown(conn, path) =~ "(#{mailto})"
    end
  end

  test "each page and its Markdown link a booking address only when one is set", %{conn: conn} do
    for path <- paths() do
      refute has?(page(conn, path), ~s|#contact a:not([href^="mailto:"])[target="_blank"]|)
      refute markdown(conn, path) =~ "calendar.example"
    end

    Application.put_env(:techtree, :book_call, @booking)
    on_exit(fn -> Application.put_env(:techtree, :book_call, nil) end)

    for path <- paths() do
      page = page(conn, path)
      assert hrefs(page, "#opening .rg-button--primary") == [@booking]
      assert has?(page, ~s|#contact a[href="#{@booking}"][target="_blank"]|)
      assert markdown(conn, path) =~ "(#{@booking})"
    end
  end

  defp paths, do: Enum.map(Services.all() ++ [Services.security()], &Services.path(&1.id))

  defp plain({text, _href}), do: text
  defp plain(text), do: text

  defp page(conn, path), do: conn |> get(path) |> html_response(200) |> LazyHTML.from_document()

  defp markdown(conn, path),
    do: conn |> put_req_header("accept", "text/markdown") |> get(path) |> response(200)

  defp has?(page, selector), do: not Enum.empty?(LazyHTML.query(page, selector))

  defp ids(page, selector),
    do: for(node <- LazyHTML.query(page, selector), do: attribute(node, "id"))

  defp hrefs(page, selector),
    do: for(node <- LazyHTML.query(page, selector), do: attribute(node, "href"))

  defp texts(page, selector),
    do: for(node <- LazyHTML.query(page, selector), do: node |> LazyHTML.text() |> String.trim())

  defp text(page, selector),
    do: page |> LazyHTML.query(selector) |> LazyHTML.text() |> String.trim()

  defp attribute(node, name), do: node |> LazyHTML.attribute(name) |> List.first()
end
