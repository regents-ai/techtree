defmodule TechtreeWeb.MethodSurface do
  @moduledoc """
  Return accurate method refusals for public catalog and publication routes.
  The shared private profile adapter owns its authenticated method responses.
  """

  @behaviour Plug

  alias TechtreeWeb.ExactResponse

  @mutations ~w(POST PUT PATCH DELETE)

  # A `GET` route answers `HEAD` too; nothing else on this site is implied by
  # anything else.
  @implied [{"GET", ["GET", "HEAD"]}, {"PATCH", ["PATCH"]}, {"POST", ["POST"]}]

  @impl Plug
  def init(opts), do: opts

  @impl Plug
  def call(%Plug.Conn{method: method} = conn, _opts) when method in @mutations do
    case answered(conn) do
      [] ->
        conn

      methods ->
        if method in methods do
          conn
        else
          conn
          |> Plug.Conn.put_resp_header("allow", Enum.join(methods, ", "))
          |> ExactResponse.send_error(
            405,
            :method_not_allowed,
            refusal(conn.request_path, methods),
            false
          )
          |> Plug.Conn.halt()
        end
    end
  end

  @impl Plug
  def call(conn, _opts), do: conn

  defp answered(conn) do
    Enum.flat_map(@implied, fn {method, implied} ->
      if is_map(
           Phoenix.Router.route_info(TechtreeWeb.Router, method, conn.request_path, conn.host)
         ),
         do: implied,
         else: []
    end)
  end

  defp refusal("/api/v1/publications", _methods),
    do: "this address accepts one kind of signed document, and nothing else"

  defp refusal("/api/v1/profile" <> _rest, _methods),
    do: "use the documented method for this private profile action"

  defp refusal(_path, _methods), do: "this address publishes and does not accept anything"
end
