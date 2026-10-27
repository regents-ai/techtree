defmodule TechtreeWeb.VisitLog.Events do
  @moduledoc """
  Turns the framework's own `:telemetry` events into visit lines
  (`TechtreeWeb.VisitLog.record/4`); a page's own `page` line comes from
  `TechtreeWeb.VisitLog.on_mount/4`:

  - `request`: a page or file answered over HTTP, by route and outcome.
  - `tool.call`: an `/api` call, named by the tool or command the caller gave in
    `x-regent-client`, else by its route; the outcome is `ok` or the error code
    the answer carried; `client` names the program that called.
  - `press`: an event a page or one of its components handled, as `View:event`.
    A wallet step reports what the wallet answered: `sent`, `signed` or why
    nothing was sent.
  - `action`: an Ash create, update, destroy or generic action, as
    `resource.action`, with its time.
  - `job`: a background job's run, by worker and how it ended.
  - `outgoing`: a call to another site, by method and host, and its status.
  - `step` `signed_in`: the browser's sign-in exchange succeeded.

  Actions and outgoing calls are written only inside a request, page or job, so
  the chain reader's own polling writes nothing.
  """

  alias TechtreeWeb.VisitLog

  # The reasons the wallet hook reports (`Failure` in send_step.ts).
  @wallet_failures ~w(step_unknown wallet_unavailable network_mismatch wallet_declined insufficient_funds send_unconfirmed)
  @domain_apps [:techtree, :regent_identity, :regent_credits, :regent_agents, :regent_points]

  @doc "Attaches every handler; called once at start."
  def attach,
    do: :telemetry.attach_many("techtree-visit-log", events(), &__MODULE__.handle/4, nil)

  defp events do
    ash =
      for app <- @domain_apps,
          domain <- Application.fetch_env!(app, :ash_domains),
          kind <- [:create, :update, :destroy, :action],
          do: [:ash, Ash.Domain.Info.short_name(domain), kind, :stop]

    [
      [:phoenix, :endpoint, :stop],
      [:phoenix, :live_view, :handle_event, :stop],
      [:phoenix, :live_view, :handle_event, :exception],
      [:phoenix, :live_component, :handle_event, :stop],
      [:phoenix, :live_component, :handle_event, :exception],
      [:oban, :job, :start],
      [:oban, :job, :stop],
      [:oban, :job, :exception],
      [:finch, :request, :stop]
    ] ++ ash
  end

  @doc false
  def handle([:phoenix, :endpoint, :stop], %{duration: duration}, %{conn: conn}, _config) do
    unless quiet?(conn) do
      Logger.metadata(
        actor: VisitLog.actor(conn.assigns[:actor] || conn.assigns[:current_human_account])
      )

      route = VisitLog.route(TechtreeWeb.Router, conn.method, conn.request_path, conn.host)

      case conn.path_info do
        ["api" | _] ->
          VisitLog.record(
            "tool.call",
            VisitLog.client(conn) || route,
            answer(conn),
            ms(duration),
            VisitLog.caller(conn)
          )

        _page ->
          requested(conn, route, ms(duration))
      end
    end
  end

  def handle([:phoenix, :live_view, :handle_event, ending], measurements, metadata, _config) do
    remember(metadata.socket)
    pressed(metadata.socket.view, ending, measurements, metadata)
  end

  # A component runs in its page's process and has none of the page's assigns, so
  # the page's own `actor` stays.
  def handle([:phoenix, :live_component, :handle_event, ending], measurements, metadata, _config),
    do: pressed(metadata.component, ending, measurements, metadata)

  # A job runs in its own process; its lines say so, and carry no visit.
  def handle([:oban, :job, :start], _measurements, _metadata, _config),
    do: Logger.metadata(surface: "job", visit: nil, actor: nil)

  def handle([:oban, :job, _ending], %{duration: duration}, %{job: job, state: state}, _config),
    do: VisitLog.record("job", VisitLog.short(job.worker), state, ms(duration))

  def handle(
        [:finch, :request, :stop],
        %{duration: duration},
        %{request: request, result: result},
        _config
      ) do
    if Logger.metadata()[:surface] do
      VisitLog.record(
        "outgoing",
        "#{request.method} #{request.host}",
        reply(result),
        ms(duration)
      )
    end
  end

  def handle([:ash, _domain, _kind, :stop], %{duration: duration}, metadata, _config) do
    if Logger.metadata()[:surface] do
      VisitLog.record(
        "action",
        "#{metadata.resource_short_name}.#{metadata.action}",
        nil,
        ms(duration)
      )
    end
  end

  defp pressed(owner, ending, measurements, metadata) do
    outcome = if ending == :exception, do: "failed", else: wallet(metadata.event, metadata.params)

    VisitLog.record(
      "press",
      "#{VisitLog.short(owner)}:#{metadata.event}",
      outcome,
      ms(measurements[:duration])
    )
  end

  defp requested(conn, route, ms) do
    VisitLog.record("request", route, answer(conn), ms)
    if signed_in?(conn, route), do: VisitLog.step("signed_in")
  end

  defp signed_in?(%Plug.Conn{method: "POST", status: status}, "/auth/privy/session"),
    do: status in 200..299

  defp signed_in?(_conn, _route), do: false

  # The health check and the browser's own reports would only describe themselves.
  defp quiet?(%Plug.Conn{path_info: ["healthz"]}), do: true
  defp quiet?(%Plug.Conn{path_info: ["visit-log"]}), do: true
  defp quiet?(_conn), do: false

  # A page's account can change while it is open, so each line reads it afresh.
  defp remember(socket),
    do: Logger.metadata(actor: VisitLog.actor(socket.assigns[:access_context]))

  defp answer(%Plug.Conn{status: status}) when status in 200..399, do: "ok"

  defp answer(conn) do
    with body when not is_nil(body) <- conn.resp_body,
         {:ok, %{"error" => %{"code" => code}}} when is_binary(code) <-
           Jason.decode(IO.iodata_to_binary(body)) do
      code
    else
      _no_code -> "status_#{conn.status}"
    end
  end

  defp wallet("step_sent", _params), do: "sent"
  defp wallet("step_signed", _params), do: "signed"
  defp wallet("step_failed", %{"reason" => reason}) when reason in @wallet_failures, do: reason
  defp wallet("step_failed", _params), do: "other"
  defp wallet(_event, _params), do: "ok"

  defp reply({:ok, %Finch.Response{status: status}}), do: Integer.to_string(status)
  defp reply({:ok, _streamed}), do: "ok"

  defp reply({:error, %{__struct__: error}}),
    do: error |> VisitLog.short() |> String.downcase() |> String.replace(".", "_")

  defp reply(_other), do: "error"

  defp ms(nil), do: nil
  defp ms(duration), do: System.convert_time_unit(duration, :native, :millisecond)
end
