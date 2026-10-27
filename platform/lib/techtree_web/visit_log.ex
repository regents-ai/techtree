defmodule TechtreeWeb.VisitLog do
  @moduledoc """
  One log line for each thing a person or agent did, what the site did about it
  and how it ended, so a visit can be replayed from the lines
  (ash-template's docs/logging-replay-plan.md).

  Every line carries the same few fields and nothing else: in production the
  JSON formatter writes only the `visit`, `actor`, `surface`, `request_id` and
  `event` metadata (config/runtime.exs), and `record/4` keeps only an event's
  name, where it happened, its outcome and how long it took. Free text never
  reaches a line: names, routes and tool names come from the site's own code or
  from a short header checked against a pattern, and anything else is written as
  `other`.

  - `visit`: a random id for one browser visit, kept in the `_visit` cookie until
    the browser closes and sent by the page's own scripts in `x-regent-visit`
    when they send no cookies. It is not tied to the account. Calls from outside
    a page have none.
  - `actor`: `person:` or `agent:` and a one-way code for the account or agent,
    or `anonymous`. The code cannot be turned back into the account.
  - `surface`: `page`, `webmcp`, `cli`, `agent_http` or `job`. The page's tools
    say `x-regent-client: webmcp/<tool>`; Regents CLI says
    `regents-cli/<version> <command>`. An API call that names neither but
    carries a visit is the page's own script, so it is `page`.

  A `tool.call` line also names its `client`: `webmcp`, `regents-cli/<version>`,
  another program's `<name>/<version>` as its `x-regent-client` gave them,
  `other` for a header that gives neither, or `none`.

  The events themselves come from `TechtreeWeb.VisitLog.Events`; the browser
  adds the few only it can see through `TechtreeWeb.VisitLogController`.

  Two kinds of line show where people come from and where they stop, the same
  on every site:

  - `arrival`: the first page of a visit, once its page has connected (so a
    crawler that runs no script writes none), by route and where the visit came
    from: a name from `sources/0` (from `utm_source`, else the referring site),
    `site` for this site, `other_site` for any other, or `direct`. The referring
    address itself is never written.
  - `step`: one of `steps/0`, the shared journey from first look to a paired
    agent, with the agent's harness where there is one.

  A browser that sends Global Privacy Control (`Sec-GPC: 1`) writes neither, on
  any page of its visit; its other lines are written as everyone's are.
  """

  @behaviour Plug

  require Logger

  import Plug.Conn

  @cookie "_visit"
  # Set in each request's and page's process when its browser sent Global Privacy Control.
  @gpc {__MODULE__, :gpc}
  @visit ~r/\A[A-Za-z0-9_-]{22}\z/
  @webmcp ~r/\Awebmcp\/([a-z][a-z0-9_]{0,63})\z/
  @cli ~r/\Aregents-cli\/([0-9A-Za-z.+-]{1,32}) ([a-z0-9][a-z0-9 _-]{0,63})\z/
  @program ~r/\A([a-z][a-z0-9._-]{0,31}\/[0-9][0-9A-Za-z.+-]{0,31})(?: |\z)/
  @where ~r/\A[A-Za-z0-9_.:\/@* -]{1,120}\z/
  @outcome ~r/\A[a-z0-9_]{1,48}\z/
  @names ~w(request tool.call page press action job outgoing page.error tool.unsent press.unsent arrival step)
  @steps ~w(sign_in_opened signed_in pairing_code_shown agent_paired)
  # Where a visit came from, by the referring site's address or `utm_source`.
  @sources %{
    "chatgpt.com" => "chatgpt",
    "chat.openai.com" => "chatgpt",
    "perplexity.ai" => "perplexity",
    "claude.ai" => "claude",
    "gemini.google.com" => "gemini",
    "copilot.microsoft.com" => "copilot",
    "google.com" => "google",
    "bing.com" => "bing",
    "duckduckgo.com" => "duckduckgo",
    "x.com" => "x",
    "twitter.com" => "x",
    "t.co" => "x",
    "linkedin.com" => "linkedin",
    "lnkd.in" => "linkedin",
    "github.com" => "github",
    "news.ycombinator.com" => "hackernews",
    "reddit.com" => "reddit"
  }

  @doc "The metadata a production line carries (config/runtime.exs)."
  def fields, do: [:request_id, :visit, :actor, :surface, :event]

  @doc "The named steps of the shared journey."
  def steps, do: @steps

  @doc "The names an arrival can give for where it came from, besides `site`, `other_site` and `direct`."
  def sources, do: @sources |> Map.values() |> Enum.uniq()

  @doc """
  Writes one `step` line: one of `steps/0`, with the agent's harness where there
  is one. Nothing is written for a browser that sends Global Privacy Control.
  """
  def step(name, harness \\ nil) when name in @steps do
    unless Process.get(@gpc), do: record("step", name, harness)
    :ok
  end

  @doc "Writes one event line (`event/4`); its message is its name, where and outcome."
  def record(name, where, outcome \\ nil, ms \\ nil, client \\ nil) do
    event = event(name, where, outcome, ms, client)
    message = Enum.join([event.name, event.where | List.wrap(event[:outcome])], " ")
    Logger.info(fn -> {message, event: event} end)
  end

  @doc """
  One event. `where` and `outcome` that do not fit their pattern are written as
  `other`; `ms` is a whole number of milliseconds or left out; `client` is one of
  `caller/1`'s answers or left out.
  """
  def event(name, where, outcome, ms, client \\ nil) when name in @names do
    %{
      name: name,
      where: fit(where, @where),
      outcome: outcome && fit(outcome, @outcome),
      ms: ms,
      client: client
    }
    |> Map.reject(fn {_key, value} -> is_nil(value) end)
  end

  defp fit(value, pattern) when is_binary(value),
    do: if(Regex.match?(pattern, value), do: value, else: "other")

  defp fit(value, pattern) when is_atom(value), do: fit(Atom.to_string(value), pattern)
  defp fit(_value, _pattern), do: "other"

  @doc "The one-way code for who acted: an account, a signed-in agent, or nobody."
  def actor(%Techtree.Actors.Agent{agent_id: id}), do: "agent:" <> code(id)
  def actor(%Techtree.Accounts.HumanAccount{id: id}), do: "person:" <> code(id)
  def actor(%Techtree.AccessContext{principal: {:human, account}}), do: actor(account)
  def actor(_nobody), do: "anonymous"

  defp code(id) do
    :crypto.mac(:hmac, :sha256, key(), to_string(id))
    |> binary_part(0, 8)
    |> Base.encode16(case: :lower)
  end

  # Derived from the endpoint's secret, so the codes cannot be recomputed from
  # account ids without it, and stay the same across machines and releases.
  defp key do
    case :persistent_term.get(__MODULE__, nil) do
      nil ->
        key =
          TechtreeWeb.Endpoint.config(:secret_key_base)
          |> Plug.Crypto.KeyGenerator.generate("visit log actor", length: 32)

        :persistent_term.put(__MODULE__, key)
        key

      key ->
        key
    end
  end

  @doc "Where a request or page lands, as its route (`/rooms/:room`), never its own path."
  def route(router, method, path, host) do
    case Phoenix.Router.route_info(router, method, path, host) do
      %{route: route} -> route
      :error -> "unmatched"
    end
  end

  @doc "Short module names: `RoomsLive`, not `TechtreeWeb.RoomsLive`."
  def short(module) when is_atom(module), do: module |> inspect() |> short()

  def short(name) when is_binary(name),
    do:
      name
      |> String.replace_prefix("TechtreeWeb.", "")
      |> String.replace_prefix("Techtree.", "")

  # Plug: every request through the endpoint, before the router.

  @impl Plug
  def init(opts), do: opts

  @impl Plug
  def call(conn, _opts) do
    conn = fetch_cookies(conn)
    {surface, client} = surface(conn)
    {conn, visit} = visit(conn, surface)
    surface = if surface == "agent_http" and visit, do: "page", else: surface
    Logger.metadata(visit: visit, surface: surface)
    Process.put(@gpc, gpc?(conn))

    conn
    |> assign(:visit, visit)
    |> assign(:gpc, gpc?(conn))
    |> put_private(:visit_log_client, client)
    |> put_private(:visit_log_caller, caller(conn, surface))
  end

  # The program that made an API call, as its `x-regent-client` names it.
  defp caller(%Plug.Conn{path_info: ["api" | _]} = conn, surface) do
    case {surface, get_req_header(conn, "x-regent-client")} do
      {"webmcp", _sent} -> "webmcp"
      {_surface, []} -> "none"
      {_surface, [sent | _]} -> program(sent)
    end
  end

  defp caller(_conn, _surface), do: nil

  defp program(sent) do
    case Regex.run(@program, sent) do
      [_all, program] -> program
      nil -> "other"
    end
  end

  # A page keeps its cookie's visit, and a page opened without one starts a visit.
  # An API call takes the visit its page's script sent, in the header when it
  # sends no cookies, or in the cookie when it does.
  defp visit(conn, "page") do
    case conn.cookies[@cookie] do
      visit when is_binary(visit) ->
        if Regex.match?(@visit, visit), do: {conn, visit}, else: start(conn)

      nil ->
        if page?(conn), do: start(conn), else: {conn, nil}
    end
  end

  defp visit(conn, _surface) do
    sent = get_req_header(conn, "x-regent-visit") ++ List.wrap(conn.cookies[@cookie])
    {conn, Enum.find(sent, &Regex.match?(@visit, &1))}
  end

  defp start(conn) do
    visit = 16 |> :crypto.strong_rand_bytes() |> Base.url_encode64(padding: false)

    conn =
      conn
      |> put_resp_cookie(@cookie, visit,
        http_only: true,
        same_site: "Lax",
        secure: conn.scheme == :https
      )
      |> assign(:arrival, unless(gpc?(conn), do: arrival(conn)))

    {conn, visit}
  end

  @doc "Whether the browser sent Global Privacy Control: no `arrival` or `step` lines for it."
  def gpc?(conn), do: get_req_header(conn, "sec-gpc") == ["1"]

  @doc "Where a visit that starts with this request came from (see the moduledoc)."
  def arrival(conn) do
    conn = fetch_query_params(conn)

    with nil <- source(conn.query_params["utm_source"]),
         [referrer | _] <- get_req_header(conn, "referer"),
         %URI{host: host} when is_binary(host) <- URI.parse(referrer) do
      cond do
        host == conn.host -> "site"
        source = source(host) -> source
        true -> "other_site"
      end
    else
      source when is_binary(source) -> source
      _no_referrer -> "direct"
    end
  end

  # A site's address, with or without `www.` or another part in front, or a
  # source's own name (`utm_source=chatgpt`).
  defp source(name) when is_binary(name) do
    name = name |> String.downcase() |> String.replace_prefix("www.", "")

    @sources[name] ||
      Enum.find_value(@sources, fn {site, source} ->
        if String.ends_with?(name, "." <> site), do: source
      end) ||
      if(name in sources(), do: name)
  end

  defp source(_nothing), do: nil

  # Only a browser opening a page asks for HTML; health checks and API calls don't.
  defp page?(conn),
    do: conn |> get_req_header("accept") |> Enum.any?(&String.contains?(&1, "text/html"))

  defp surface(%Plug.Conn{path_info: ["api" | _]} = conn) do
    client = conn |> get_req_header("x-regent-client") |> List.first("")

    cond do
      match = Regex.run(@webmcp, client) -> {"webmcp", Enum.at(match, 1)}
      match = Regex.run(@cli, client) -> {"cli", "#{Enum.at(match, 2)}@#{Enum.at(match, 1)}"}
      true -> {"agent_http", nil}
    end
  end

  defp surface(_conn), do: {"page", nil}

  @doc "The tool or command the caller named in `x-regent-client`, if any."
  def client(conn), do: conn.private[:visit_log_client]

  @doc "The program that made an API call (see the moduledoc); nil for anything else."
  def caller(conn), do: conn.private[:visit_log_caller]

  # on_mount, for every LiveView (TechtreeWeb.live_view/0). The connected page
  # runs in its own process, so it takes the visit its first render passed on
  # (TechtreeWeb.Live.Session.render_context/1). A page the router opened writes
  # a `page` line when it opens and each time its address changes, whether or not
  # it handles params itself; a view drawn inside another page is part of that page.
  # The first page of a visit writes its `arrival` line first. The page keeps the
  # session it was drawn with across moves to other pages and reconnects, so only
  # the first connection of the page as loaded writes it: a reconnect counts
  # `_mounts` above 0, and a move to another page names the page it left.
  def on_mount(:default, _params, session, socket) do
    visit = session["visit"]

    Logger.metadata(visit: visit, surface: "page", actor: actor(socket.assigns[:access_context]))
    Process.put(@gpc, session["gpc"] == true)

    socket =
      Phoenix.Component.assign(socket, visit: visit, arrival: first_arrival(session, socket))

    if socket.router,
      do: {:cont, Phoenix.LiveView.attach_hook(socket, :visit_log_page, :handle_params, &page/3)},
      else: {:cont, socket}
  end

  defp first_arrival(session, socket) do
    with true <- Phoenix.LiveView.connected?(socket),
         %{"_mounts" => 0} = params <- Phoenix.LiveView.get_connect_params(socket),
         nil <- params["_live_referer"] do
      session["arrival"]
    else
      _not_the_first -> nil
    end
  end

  defp page(_params, uri, socket) do
    if Phoenix.LiveView.connected?(socket) do
      %URI{path: path, host: host} = URI.parse(uri)
      Logger.metadata(actor: actor(socket.assigns[:access_context]))
      route = route(socket.router, "GET", path, host)
      if arrival = socket.assigns.arrival, do: record("arrival", route, arrival)
      record("page", route)
      {:cont, Phoenix.Component.assign(socket, :arrival, nil)}
    else
      {:cont, socket}
    end
  end
end
