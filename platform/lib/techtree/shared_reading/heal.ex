defmodule Techtree.SharedReading.Heal do
  @moduledoc """
  Asks the producer of one kind of shared reading to read all its keys again
  (`Techtree.SharedReading.heal/1`). The site's schedule runs it each minute
  for every kind a producer rereads on notice, because a notice is sent at most
  once and can be lost. One attempt: the next minute's run replaces a failed one.
  """

  use Oban.Worker, queue: :default, max_attempts: 1

  @impl Oban.Worker
  def perform(%Oban.Job{args: %{"kind" => kind}}),
    do: kind |> String.to_existing_atom() |> Techtree.SharedReading.heal()
end
