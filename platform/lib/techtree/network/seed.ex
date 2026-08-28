defmodule Techtree.Network.Seed do
  @moduledoc """
  Putting this project's own certification runs on the log, through the door
  everybody else uses.

  A log that launches empty is a log that looks abandoned during the one week
  it most needs not to. The honest way to fill it is not with invented rows: it
  is with the runs this release was certified on, which are real, which are
  ours, and which verify.

  ## They go through the ingest and nowhere else

  There is no seeding path into the database. A submission is built out of the
  proof directory exactly as `techtree publish` would build it, and handed to
  `Techtree.Network.Ingest.accept/3` — the same function the one write address
  calls, running the same checks in the same order, taking the same refusals.
  A fixture insert would put rows on the log that no check had ever seen, and
  the log's whole claim is that everything on it was checked.

  That is also why this is a Mix task rather than a migration or a fixture.
  Seeding a live database is something an operator decides to do, to a
  database, at a moment of their choosing. A migration would do it to every
  database that ever runs, including a developer's, including a test's, and
  would do it as a schema change, which it is not.

  ## Running it twice does nothing twice

  The ingest is idempotent by bundle digest, because a participant's retry
  after a lost response has to be. That property is not re-implemented here and
  is not guarded here: running this task again sends the same bytes, the ingest
  answers `:existing`, and the log is unchanged. There is nothing to make safe
  because it already is.

  ## They carry no label saying they are ours

  Nothing a submitter writes is rendered anywhere on this site, and that
  includes us. These entries are identified by the fingerprint of the key that
  signed them, exactly as anybody else's are. What the log page carries is one
  sentence saying its first entries are this project's certification runs — a
  statement the page makes about itself, which a reader can weigh, rather than
  a badge on a row, which would be an unverifiable claim in the one place this
  design has no unverifiable claims.

  ## The proof directories are read and never written

  A completed run's files are final. This module opens them, reads their bytes
  and closes them, and the submission it builds is held in memory.
  """

  alias Techtree.Canonical
  alias Techtree.Network.Ingest
  alias Techtree.Network.Key

  @schema_version "techtree.publication-submission.v1alpha1"
  @manifest "bundle.json"

  @certification_runs [
    "run_c4758ddb5bba4023aa3530b47f4582e9",
    "run_55159aeb30c44982b8143f61b078a4db",
    "run_8f89ae9dea6541b187c74d86d119d8a6",
    "run_b3e25a431d3b43128deb31e99a0b6c68"
  ]

  @typedoc """
  What became of one run this task offered to the log.
  """
  @type result ::
          {String.t(), {:ok, pos_integer(), Ingest.outcome()}} | {String.t(), {:error, term()}}

  @doc """
  The runs this release was certified on, in the order they were executed.

  Three are the certification executions themselves and one is the founder's
  own walkthrough. They are named here rather than discovered, because which
  runs these are is the whole content of this task: a task that seeded whatever
  it found in a directory would seed whatever happened to be in that directory.
  """
  @spec certification_runs() :: [String.t()]
  def certification_runs, do: @certification_runs

  @doc """
  Offer every certification run to the log, in order.

  `runs_directory` is the directory holding one subdirectory per run, each with
  a `proof` directory inside it. It is named by the caller rather than guessed
  from the operating system, because an operator seeding a live log should be
  looking at the path they are seeding from.

  Returns one result per run, in order. A run whose proof directory is not
  there, or whose submission the log refuses, is reported and does not stop the
  ones after it: three runs on the log and one to look into is a better outcome
  than nothing on the log and one to look into.
  """
  @spec seed(Path.t(), Key.t(), String.t()) :: [result()]
  def seed(runs_directory, %Key{} = key, origin) do
    Enum.map(@certification_runs, fn run_id ->
      {run_id, offer(Path.join([runs_directory, run_id, "proof"]), key, origin)}
    end)
  end

  @doc """
  The exact bytes `techtree publish` puts on the wire for one proof directory.

  Four members and no fifth, the files keyed by their POSIX path inside the
  directory against the base64 of their stored bytes, and the whole document in
  the canonical encoding both halves of this protocol share. The two claims the
  document makes about the bundle — which run it is and which digest it is
  filed under — are read out of the bundle's own signed manifest, which is what
  an honest sender does and the only thing a sender could honestly do.

  The whole directory travels rather than the manifest's own list of artifacts,
  because the manifest does not commit to itself and a submission without it is
  a submission nothing can be checked against.
  """
  @spec submission(Path.t()) :: binary()
  def submission(proof_directory) do
    files = files(proof_directory)
    manifest = files |> Map.fetch!(@manifest) |> Jason.decode!()

    Canonical.encode!(%{
      "schema_version" => @schema_version,
      "run_id" => manifest["payload"]["run_id"],
      "bundle_digest" => manifest["payload_digest"],
      "files" => Map.new(files, fn {path, bytes} -> {path, Base.encode64(bytes)} end)
    })
  end

  defp offer(proof_directory, key, origin) do
    if File.dir?(proof_directory) do
      case Ingest.accept(submission(proof_directory), key, origin: origin) do
        {:ok, entry, outcome} -> {:ok, entry.log_sequence, outcome}
        {:error, error} -> {:error, error}
      end
    else
      {:error, :no_proof_directory}
    end
  end

  defp files(proof_directory) do
    proof_directory
    |> Path.join("**")
    |> Path.wildcard(match_dot: true)
    |> Enum.filter(&File.regular?/1)
    |> Map.new(&{Path.relative_to(&1, proof_directory), File.read!(&1)})
  end
end
