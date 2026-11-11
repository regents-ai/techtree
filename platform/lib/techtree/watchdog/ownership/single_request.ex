defmodule Techtree.Watchdog.Ownership.SingleRequest do
  @moduledoc """
  The `Req` adapter for the well-known proof fetch: one GET over its own Mint
  connection, closed whatever happens.

  The request's URL carries the address `Techtree.Watchdog.Ownership` already
  checked, and `connect_options[:hostname]` the customer's host name, which
  Mint uses for TLS SNI, certificate verification and the `Host` header. The
  address is connected to as it is, never looked up again. There is no pool,
  so nothing outlives the request and nothing is created per host. Connecting
  gives up after `connect_options[:timeout]` (any `connect_options[:transport_opts]`
  go to the TLS socket as well), the whole answer must arrive
  within `receive_timeout`, and at most 4 KiB of the body are read.
  """

  @max_body_bytes 4_096

  @doc "Sends `request` and returns its response, or the error that stopped it."
  @spec run(Req.Request.t()) :: {Req.Request.t(), Req.Response.t() | Exception.t()}
  def run(%Req.Request{url: url, options: options} = request) do
    {:ok, address} = :inet.parse_address(String.to_charlist(url.host))

    connect_options = [
      hostname: options.connect_options[:hostname],
      mode: :passive,
      protocols: [:http1],
      transport_opts:
        Keyword.merge(
          [timeout: options.connect_options[:timeout]],
          Keyword.get(options.connect_options, :transport_opts, [])
        )
    ]

    case Mint.HTTP.connect(:https, address, url.port, connect_options) do
      {:ok, conn} ->
        try do
          {request, exchange(conn, request, deadline(options.receive_timeout))}
        after
          Mint.HTTP.close(conn)
        end

      {:error, error} ->
        {request, error}
    end
  end

  defp exchange(conn, request, deadline) do
    headers = for {name, values} <- request.headers, value <- values, do: {name, value}

    case Mint.HTTP.request(conn, "GET", request.url.path, headers, nil) do
      {:ok, conn, ref} -> receive_response(conn, ref, deadline, %{headers: [], body: ""})
      {:error, _conn, error} -> error
    end
  end

  defp receive_response(conn, ref, deadline, response) do
    case Mint.HTTP.recv(conn, 0, remaining(deadline)) do
      {:ok, conn, parts} ->
        case Enum.reduce_while(parts, {:more, response}, &take(&1, ref, &2)) do
          {:done, response} -> Req.Response.new(response)
          {:more, response} -> receive_response(conn, ref, deadline, response)
        end

      {:error, _conn, error, _parts} ->
        error
    end
  end

  defp take({:status, ref, status}, ref, {:more, response}),
    do: {:cont, {:more, Map.put(response, :status, status)}}

  defp take({:headers, ref, headers}, ref, {:more, response}),
    do: {:cont, {:more, %{response | headers: response.headers ++ headers}}}

  defp take({:data, ref, data}, ref, {:more, response}) do
    body = response.body <> data

    if byte_size(body) > @max_body_bytes,
      do: {:halt, {:done, %{response | body: binary_part(body, 0, @max_body_bytes)}}},
      else: {:cont, {:more, %{response | body: body}}}
  end

  defp take({:done, ref}, ref, {:more, response}), do: {:halt, {:done, response}}
  defp take(_other, _ref, state), do: {:cont, state}

  defp deadline(timeout), do: System.monotonic_time(:millisecond) + timeout

  defp remaining(deadline), do: max(deadline - System.monotonic_time(:millisecond), 0)
end
