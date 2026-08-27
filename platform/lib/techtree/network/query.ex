defmodule Techtree.Network.Query do
  @moduledoc """
  Everything the public surface is allowed to ask about the run log.

  The pages and the one read endpoint call this module and nothing else, the
  way they call `Techtree.Catalog.Query` for the catalog. Two rules live here
  so that they cannot be forgotten anywhere else.

  *The log is ordered by arrival.* Newest first, by the position the database
  handed out. There is no order by score, no rank, and no argument for one
  available to a caller — the Climb's own manifest says there is no
  leaderboard, and an ordering is a ranking whatever it is called.

  *A withdrawn entry is not on the log.* It is not in the list, and its own page
  says it was withdrawn and shows nothing else. That is why the list and the
  lookup are two different questions here: withdrawing something has to remove
  it from the log without making its address a lie.

  Nothing in this module can see a contributor address. There is no read for
  one, so no page could render one by accident.
  """

  alias Techtree.Network
  alias Techtree.Network.Submission

  @doc """
  The log, newest arrival first, without the withdrawn entries.
  """
  @spec list_entries() :: [Submission.t()]
  def list_entries, do: Network.list_published_submissions!()

  @doc """
  One entry by the digest of the bundle it published, withdrawn or not.
  """
  @spec get_entry(String.t()) :: {:ok, Submission.t()} | :error
  def get_entry(digest) when is_binary(digest) do
    case Network.get_submission_by_digest(digest) do
      {:ok, %Submission{} = submission} -> {:ok, submission}
      _other -> :error
    end
  end

  @doc """
  Whether an entry has been withdrawn.
  """
  @spec withdrawn?(Submission.t()) :: boolean()
  def withdrawn?(%Submission{withdrawn_at: withdrawn_at}), do: not is_nil(withdrawn_at)
end
