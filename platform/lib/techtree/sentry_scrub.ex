defmodule Techtree.SentryScrub do
  @moduledoc """
  Strips what a crash can carry of a signing key or a page's assigns before an
  event leaves for Sentry: each stack frame's arguments, and a crashed
  process's state and last message.
  """

  alias Sentry.Event
  alias Sentry.Interfaces.Stacktrace

  @crash_extra [:genserver_state, :last_message, :pid_which_sent_last_message]

  @spec scrub(Event.t()) :: Event.t()
  def scrub(%Event{} = event) do
    %{
      event
      | exception: Enum.map(event.exception, &without_args/1),
        threads: event.threads && Enum.map(event.threads, &without_args/1),
        extra: Map.drop(event.extra, @crash_extra)
    }
  end

  defp without_args(%{stacktrace: %Stacktrace{frames: frames} = stacktrace} = part),
    do: %{part | stacktrace: %{stacktrace | frames: Enum.map(frames, &%{&1 | vars: nil})}}

  defp without_args(part), do: part
end
