defmodule TechtreeWeb.PublicationAddress do
  @moduledoc """
  Whether a request is a post to the one address that accepts a body.

  The plugs in front of the parser have to agree with the routing table about
  which requests reach `PublicationController.create`, or a request the router
  sends there could skip them. So the address is matched the way the router
  matches it: by its segments, each one percent-decoded, so a trailing slash or
  an escaped letter is the same address.
  """

  @segments ["api", "v1", "publications"]
  @model_climb_segments ["api", "model-climb", "v1", "reports"]

  @doc """
  True for a `POST` the routing table would send to the publication address.
  """
  @spec post?(Plug.Conn.t()) :: boolean()
  def post?(%Plug.Conn{method: "POST", path_info: path_info}),
    do: Enum.map(path_info, &URI.decode/1) == @segments

  def post?(%Plug.Conn{}), do: false

  @doc """
  True for a `POST` the routing table would send to the Model Climb proof
  address, which accepts a body under the same budget.
  """
  @spec model_climb_post?(Plug.Conn.t()) :: boolean()
  def model_climb_post?(%Plug.Conn{method: "POST", path_info: path_info}),
    do: Enum.map(path_info, &URI.decode/1) == @model_climb_segments

  def model_climb_post?(%Plug.Conn{}), do: false
end
