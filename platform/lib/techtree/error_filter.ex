defmodule Techtree.ErrorFilter do
  @moduledoc """
  Keeps only where an error happened before it is saved: the request's host, path
  and method, the page, component and event names, and the job's worker, queue
  and attempt. Headers, addresses, query strings, parameters and job arguments
  can carry a signing key, a session or a person's details, so none is kept.
  """

  @behaviour ErrorTracker.Filter

  @kept ~w(
    request.host request.path request.method
    live_view.view live_view.component live_view.event
    job.id job.worker job.queue job.attempt job.priority
  )

  @impl ErrorTracker.Filter
  def sanitize(context), do: Map.take(context, @kept)
end
