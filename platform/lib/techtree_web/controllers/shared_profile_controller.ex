defmodule TechtreeWeb.SharedProfileController do
  use TechtreeWeb, :controller

  def read(conn, _params), do: RegentIdentity.HTTP.call(%{conn | path_info: []}, :techtree)
  def update(conn, _params), do: RegentIdentity.HTTP.call(%{conn | path_info: []}, :techtree)
  def sync(conn, _params), do: RegentIdentity.HTTP.call(%{conn | path_info: ["sync"]}, :techtree)
end
