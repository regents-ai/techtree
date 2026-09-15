defmodule Techtree.Safety.TestPack.Case do
  @moduledoc "One recorded transcript and the independent record of what happened in it."
  @enforce_keys [:id, :number, :title, :task, :events, :outcome, :record]
  defstruct [:id, :number, :title, :task, :events, :outcome, :record, :evidence_event]

  @type event :: %{
          number: pos_integer(),
          kind: :read | :shell | :write | :message,
          text: String.t()
        }
  @type t :: %__MODULE__{
          id: String.t(),
          number: pos_integer(),
          title: String.t(),
          task: String.t(),
          events: [event()],
          outcome: :violation | :compliant,
          record: String.t(),
          evidence_event: pos_integer() | nil
        }
end
