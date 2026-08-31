defmodule TechtreeWeb.NotFoundError do
  @moduledoc """
  A page was asked for something this release does not publish.

  Raising this is how a page says `404`. There is no near-miss guessing and no
  redirect to something similar: a name that resolves to nothing is answered as
  nothing.
  """

  defexception message: "not found", plug_status: 404
end
