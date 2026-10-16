defmodule Techtree.WalletBench.Changes.Operator do
  @moduledoc """
  An operator action names who ran it: the actor must be a
  `Techtree.Actors.Operator` with a name of 1 to 64 letters, digits, `_`, `.` or
  `-`. The name goes into the changeset context's `:operator`, where the event
  the action records reads it, and with `attribute: name` onto that attribute too.
  With `required: false` (an action the bench itself also takes, such as
  retiring a machine), another actor records no name.
  """

  use Ash.Resource.Change

  alias Techtree.Actors.Operator

  @name ~r/\A[a-zA-Z0-9_.-]{1,64}\z/

  @impl true
  def change(changeset, opts, %{actor: %Operator{name: name}}) when is_binary(name) do
    if Regex.match?(@name, name) do
      changeset = Ash.Changeset.set_context(changeset, %{operator: name})

      case opts[:attribute] do
        nil -> changeset
        attribute -> Ash.Changeset.force_change_attribute(changeset, attribute, name)
      end
    else
      refuse(changeset)
    end
  end

  def change(changeset, opts, _context),
    do: if(Keyword.get(opts, :required, true), do: refuse(changeset), else: changeset)

  defp refuse(changeset),
    do:
      Ash.Changeset.add_error(
        changeset,
        "An operator action needs actor: %Techtree.Actors.Operator{name: ...}, a name of 1 to 64 letters, digits, _, . or -."
      )
end
