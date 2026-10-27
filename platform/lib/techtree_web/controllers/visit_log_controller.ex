defmodule TechtreeWeb.VisitLogController do
  @moduledoc """
  The few visit lines only the browser can see (visit_log.ts), up to 20 a post:

  - `page.error`: the page hit a script error, by route; never its message.
  - `tool.unsent`: one of the page's tools got no answer from the site.
  - `press.unsent`: a wallet press never reached the site.
  - `step` `sign_in_opened`: a Sign in button was pressed.

  Each line is checked against the names, routes and outcomes the page can send;
  anything else is dropped. The answer is the same whatever was sent, and nothing
  is stored.
  """
  use TechtreeWeb, :controller

  alias TechtreeWeb.VisitLog

  @most 20
  @name ~r/\A[a-z][a-z0-9_]{0,63}\z/

  def create(conn, params) do
    Logger.metadata(actor: VisitLog.actor(conn.assigns[:current_human_account]))

    for line <- lines(params, conn.host), do: write(line)

    conn |> put_resp_header("cache-control", "no-store") |> send_resp(:no_content, "")
  end

  @doc "The lines of a post worth writing, as `{name, where, outcome}`."
  def lines(%{"lines" => lines}, host) when is_list(lines),
    do: lines |> Enum.take(@most) |> Enum.flat_map(&line(&1, host))

  def lines(_params, _host), do: []

  defp line(%{"name" => "page.error", "where" => "/" <> _ = path, "outcome" => outcome}, host)
       when outcome in ~w(error unhandledrejection),
       do: [{"page.error", VisitLog.route(TechtreeWeb.Router, "GET", path, host), outcome}]

  defp line(%{"name" => "tool.unsent", "where" => tool, "outcome" => outcome}, _host)
       when is_binary(tool) and outcome in ~w(unreachable outcome_unknown),
       do: named("tool.unsent", tool, outcome)

  defp line(%{"name" => "press.unsent", "where" => step, "outcome" => "lost"}, _host)
       when is_binary(step),
       do: named("press.unsent", step, "lost")

  defp line(%{"name" => "step", "where" => "sign_in_opened"}, _host),
    do: [{"step", "sign_in_opened", nil}]

  defp line(_untrusted, _host), do: []

  defp write({"step", step, nil}), do: VisitLog.step(step)
  defp write({name, where, outcome}), do: VisitLog.record(name, where, outcome)

  defp named(name, where, outcome),
    do: if(Regex.match?(@name, where), do: [{name, where, outcome}], else: [])
end
