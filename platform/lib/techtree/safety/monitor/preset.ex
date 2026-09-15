defmodule Techtree.Safety.Monitor.Preset do
  @moduledoc "One monitor configuration: a name and the exact prompt it runs with."
  @enforce_keys [:key, :name, :summary, :system_prompt]
  defstruct [:key, :name, :summary, :system_prompt]

  @type t :: %__MODULE__{
          key: String.t(),
          name: String.t(),
          summary: String.t(),
          system_prompt: String.t()
        }
end
