defmodule Techtree.Jobs.CursorUnmoved do
  @moduledoc """
  Refuses to move a job payments cursor another pass has moved since this pass
  read it. The check runs inside the `UPDATE`, so a pass holding an old copy
  writes nothing.
  """

  use Ash.Resource.Validation

  @impl true
  def atomic(changeset, _opts, _context) do
    from = Ash.Changeset.get_argument(changeset, :from)

    {:atomic, [:next_block], expr(next_block != ^from),
     expr(
       error(Ash.Error.Changes.StaleRecord, %{
         resource: "job payments cursor",
         filter: %{next_block: ^from}
       })
     )}
  end
end
