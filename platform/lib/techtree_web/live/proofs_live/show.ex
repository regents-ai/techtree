defmodule TechtreeWeb.ProofsLive.Show do
  @moduledoc """
  A content-addressed public proof.

  The current catalog schema contains no public-proof object kind. The route is
  reserved now, but every digest remains not found until a future, deliberately
  curated catalog release can resolve it. That is safer than treating a private
  local bundle or an arbitrary catalog object as a public proof.
  """

  use TechtreeWeb, :live_view

  @impl true
  def mount(_params, _session, _socket) do
    raise TechtreeWeb.NotFoundError, "no public proof is released under that digest"
  end
end
