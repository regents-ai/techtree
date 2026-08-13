defmodule Techtree.Catalog.Importer do
  @moduledoc """
  Ingesting one generated catalog bundle, all of it or none of it.

  The order matters and is fixed (spec section 8.10). The bundle is loaded and
  verified before the database is touched at all, so a bad bundle costs nothing.
  A release row is then opened *outside* the staging transaction — it is the only
  row that must survive a rollback, because it is where the reason for the
  rollback is written. Everything else — entry projections, the bootstrap
  payload, retiring what the new bundle dropped, retiring the previous release,
  activating this one — happens inside one transaction. A failure anywhere in it
  leaves the previously active release serving exactly what it was serving.

  Nothing in here re-encodes a protocol object. Objects are parsed to build the
  display projection, and the bytes that are served later are read from the
  bundle and hashed again; the parsed form is never written back out.
  """

  require Ash.Query
  require Logger

  alias Techtree.Catalog
  alias Techtree.Catalog.BootstrapRelease
  alias Techtree.Catalog.Bundle
  alias Techtree.Catalog.CatalogEntry
  alias Techtree.Catalog.CatalogRelease
  alias Techtree.Catalog.Error
  alias Techtree.Catalog.Verifier

  @internal [authorize?: false]

  @doc """
  Import and activate the bundle at `root`.

  Options:

    * `:channel` — the release channel to import into. Defaults to the
      configured channel, and must match the channel the bundle's bootstrap
      release declares.

  Raises `Techtree.Catalog.Error` when the bundle cannot be believed, and
  re-raises whatever made a staged import fail after the release has been marked
  failed.
  """
  @spec import!(Path.t(), keyword()) :: CatalogRelease.t()
  def import!(root, opts \\ []) do
    channel = Keyword.get_lazy(opts, :channel, &Catalog.channel/0)

    bundle = Bundle.load!(root)
    Verifier.verify_bundle!(bundle)
    check_channel!(bundle, channel)

    release =
      Catalog.begin_catalog_import!(
        %{
          channel: channel,
          catalog_digest: Bundle.catalog_digest(bundle),
          source_revision: Bundle.source_revision(bundle),
          bootstrap_digest: Bundle.bootstrap_digest(bundle)
        },
        @internal
      )

    staged =
      try do
        Ash.transact([CatalogEntry, CatalogRelease, BootstrapRelease], fn ->
          retire_previous_entries!(bundle)
          stage_entries(bundle, release)
          stage_bootstrap!(bundle, release)
          activate_release!(release)
        end)
      rescue
        exception ->
          rollback_failed_import!(release, exception)
          reraise exception, __STACKTRACE__
      end

    case staged do
      {:ok, activated} ->
        activated

      {:error, reason} ->
        rollback_failed_import!(release, reason)
        raise_import_failure(reason)
    end
  end

  @doc """
  Upsert one projection row per object the bundle ships.

  Runs inside `import!/2`'s transaction.
  """
  @spec stage_entries(Bundle.t(), CatalogRelease.t()) :: [CatalogEntry.t()]
  def stage_entries(%Bundle{} = bundle, %CatalogRelease{} = release) do
    bundle
    |> Bundle.list_entries()
    |> Enum.map(fn entry ->
      bytes = Bundle.read_entry!(bundle, entry)

      Catalog.upsert_entry_from_import!(
        entry
        |> Map.take([:kind, :reference, :relative_path, :media_type])
        |> Map.merge(%{
          protocol_digest: entry.digest,
          byte_size: byte_size(bytes),
          source_revision: release.source_revision
        })
        |> Map.merge(describe(bundle, entry, bytes)),
        @internal
      )
    end)
  end

  @doc """
  Retire every entry the newly imported bundle no longer ships.

  Runs inside `import!/2`'s transaction, before anything is staged: a public
  reference belongs to one active entry, so the entry that is losing it must let
  go of it before its replacement can take it.
  """
  @spec retire_previous_entries!(Bundle.t()) :: :ok
  def retire_previous_entries!(%Bundle{} = bundle) do
    staged = Enum.map(Bundle.list_entries(bundle), & &1.digest)

    CatalogEntry
    |> Ash.Query.filter(active == true and protocol_digest not in ^staged)
    |> Catalog.retire_entries_missing_from_import!(%{}, @internal)

    :ok
  end

  @doc """
  Store the exact bootstrap payload the bundle publishes.

  Runs inside `import!/2`'s transaction.
  """
  @spec stage_bootstrap!(Bundle.t(), CatalogRelease.t()) :: BootstrapRelease.t()
  def stage_bootstrap!(%Bundle{bootstrap: bootstrap} = bundle, %CatalogRelease{} = release) do
    Catalog.stage_bootstrap_release!(
      %{
        channel: release.channel,
        schema_version: bootstrap["schema_version"],
        raw_payload: bundle.bootstrap_bytes,
        payload_digest: Bundle.bootstrap_digest(bundle),
        cli_version: get_in(bootstrap, ["cli", "version"]),
        plugin_revision: get_in(bootstrap, ["hermes_plugin", "revision"]),
        minimum_hermes_version: get_in(bootstrap, ["minimums", "hermes_version"]),
        published_at: bootstrap["published_at"]
      },
      @internal
    )
  end

  @doc """
  Retire the previously served release, then serve this one.

  Runs inside `import!/2`'s transaction, and in this order: one active release
  per channel is a database constraint, not an intention.
  """
  @spec activate_release!(CatalogRelease.t()) :: CatalogRelease.t()
  def activate_release!(%CatalogRelease{} = release) do
    deactivate_previous(CatalogRelease, release.channel, &Catalog.deactivate_catalog_release!/2)

    deactivate_previous(
      BootstrapRelease,
      release.channel,
      &Catalog.deactivate_bootstrap_release!/2
    )

    activate_bootstrap!(release)

    release
    |> Catalog.activate_catalog_release!(@internal)
    |> Catalog.complete_catalog_import!(@internal)
  end

  @doc """
  Record, on the release that failed, why nothing was staged.

  The transaction is already rolled back by the time this runs; the release row
  survives because it was created before the transaction opened.
  """
  @spec rollback_failed_import!(CatalogRelease.t(), term()) :: CatalogRelease.t()
  def rollback_failed_import!(%CatalogRelease{} = release, reason) do
    summary = sanitize(reason)
    Logger.error("catalog import failed: #{summary}")

    Catalog.fail_catalog_import!(release, summary, %{}, @internal)
  end

  # -- Internals ------------------------------------------------------------

  defp check_channel!(%Bundle{bootstrap: bootstrap}, channel) do
    case bootstrap["channel"] do
      ^channel ->
        :ok

      other ->
        raise Error.bundle_invalid(
                "the bundle publishes a different release channel than this build serves",
                %{"expected_channel" => channel, "found_channel" => inspect(other)}
              )
    end
  end

  defp deactivate_previous(resource, channel, deactivate) do
    resource
    |> Ash.Query.filter(channel == ^channel and active == true)
    |> Ash.read!(@internal)
    |> Enum.each(&deactivate.(&1, @internal))
  end

  defp activate_bootstrap!(%CatalogRelease{} = release) do
    BootstrapRelease
    |> Ash.Query.filter(
      channel == ^release.channel and payload_digest == ^release.bootstrap_digest
    )
    |> Ash.read_one!(@internal)
    |> case do
      nil ->
        raise Error.bootstrap_missing("the import staged no bootstrap release to publish", %{
                "channel" => release.channel
              })

      bootstrap ->
        Catalog.activate_bootstrap_release!(bootstrap, @internal)
    end
  end

  # The display projection of one object. Only a Climb has one: it is the object
  # the public pages are about, and its summary is assembled from the graph the
  # Climb points at rather than from the Climb alone.
  defp describe(bundle, %{kind: :climb} = entry, bytes) do
    climb = decode!(bytes, entry.relative_path)
    metadata = fetch!(climb, ["metadata"], entry)

    campaign_digest = fetch!(climb, ["campaign_spec_digest"], entry)
    campaign = decode_object!(bundle, campaign_digest)
    policy_digest = fetch!(campaign, ["data_policy_digest"], entry)
    data_policy = decode_object!(bundle, policy_digest)
    validation_digest = fetch!(campaign, ["taskset", "validation_receipt_digest"], entry)

    %{
      title: fetch!(metadata, ["title"], entry),
      summary: fetch!(metadata, ["summary"], entry),
      status: fetch!(metadata, ["status"], entry),
      projection:
        climb_projection(%{
          entry: entry,
          climb: climb,
          metadata: metadata,
          campaign: campaign,
          campaign_digest: campaign_digest,
          data_policy: data_policy,
          policy_digest: policy_digest,
          validation_digest: validation_digest
        })
    }
  end

  defp describe(_bundle, _entry, _bytes), do: %{title: nil, summary: nil, status: nil}

  defp climb_projection(%{entry: entry, climb: climb, metadata: metadata} = parts) do
    %{campaign: campaign, data_policy: data_policy} = parts

    %{
      "reference" => entry.reference,
      "slug" => metadata["slug"],
      "version" => metadata["version"],
      "title" => metadata["title"],
      "summary" => metadata["summary"],
      "status" => metadata["status"],
      "opens_at" => metadata["opens_at"],
      "closes_at" => metadata["closes_at"],
      "climb_digest" => entry.digest,
      "campaign_spec_digest" => parts.campaign_digest,
      "data_policy_digest" => parts.policy_digest,
      "validation_receipt_digest" => parts.validation_digest,
      "purpose" => get_in(campaign, ["metadata", "purpose"]),
      "taskset_id" => get_in(campaign, ["taskset", "ref", "id"]),
      "task_count" => get_in(campaign, ["taskset", "selection", "num_tasks"]),
      "subject_harness" => get_in(campaign, ["agents", "subject", "harness", "id"]),
      "subject_harness_version" => get_in(campaign, ["agents", "subject", "harness", "version"]),
      "subject_model" => subject_model(campaign),
      "subject_runtime" =>
        take(campaign, ["agents", "subject", "runtime"], [
          "type",
          "image",
          "cpu",
          "memory_gb",
          "network_policy",
          "supported_platforms"
        ]),
      "mutation_contract" =>
        take(campaign, ["mutation_contract"], [
          "kind",
          "target_agent",
          "minimum_skills",
          "maximum_skills",
          "allowed_differences"
        ]),
      "execution" =>
        take(campaign, ["execution"], [
          "order",
          "max_concurrent",
          "retry_limit",
          "timeout_seconds"
        ]),
      "scoring" =>
        take(campaign, ["scoring"], [
          "primary_reward",
          "aggregation",
          "minimum_absolute_delta",
          "require_candidate_above_baseline"
        ]),
      "evaluation_backend" => get_in(campaign, ["evaluation_backend", "kind"]),
      "candidate_skill_visibility" => get_in(climb, ["candidate_policy", "skill_visibility"]),
      "required_mutation" => get_in(climb, ["candidate_policy", "required_mutation"]),
      "publication" =>
        take(climb, ["publication"], [
          "proof_grade",
          "report_visibility",
          "raw_episode_visibility",
          "public_trace_projection"
        ]),
      "proof_grade" => get_in(climb, ["publication", "proof_grade"]),
      "leaderboard_enabled" => get_in(climb, ["leaderboard", "enabled"]),
      "data_policy" => data_policy_summary(data_policy)
    }
  end

  # The four rights a reader most needs before starting, projected the same way
  # the CLI projects them.
  defp data_policy_summary(data_policy) do
    %{
      "raw_episode_server_upload" => get_in(data_policy, ["raw_episodes", "server_upload"]),
      "raw_episode_training_use" => get_in(data_policy, ["raw_episodes", "training_use"]),
      "candidate_skill_public_release" =>
        get_in(data_policy, ["candidate_skill", "public_release"]),
      "uplift_report_visibility" => get_in(data_policy, ["derived_artifacts", "uplift_report"])
    }
  end

  # The model is named, never credentialed: the environment variable a
  # participant would supply their own key through is not public information.
  defp subject_model(campaign) do
    take(campaign, ["agents", "subject", "model"], ["provider", "model_id", "revision"])
  end

  defp take(document, path, keys) do
    case get_in(document, path) do
      section when is_map(section) -> Map.take(section, keys)
      _other -> %{}
    end
  end

  defp decode_object!(bundle, digest) do
    bundle
    |> Bundle.read_object!(digest)
    |> Jason.decode!()
  end

  defp decode!(bytes, relative_path) do
    case Jason.decode(bytes) do
      {:ok, document} when is_map(document) ->
        document

      _other ->
        raise Error.bundle_invalid("a catalog object is not a JSON object", %{
                "path" => relative_path
              })
    end
  end

  defp fetch!(document, path, entry) do
    case get_in(document, path) do
      nil ->
        raise Error.bundle_invalid("a shipped object is missing a required field", %{
                "path" => entry.relative_path,
                "field" => Enum.join(path, ".")
              })

      value ->
        value
    end
  end

  # Whatever went wrong, the release record gets one line a stranger may read.
  defp sanitize(%Error{} = error), do: Error.summary(error)

  defp sanitize(%{__exception__: true} = exception) do
    "#{inspect(exception.__struct__)}: #{Exception.message(exception)}"
  end

  defp sanitize(reason), do: inspect(reason)

  defp raise_import_failure(%Error{} = error), do: raise(error)

  defp raise_import_failure(%{__exception__: true} = exception), do: raise(exception)

  defp raise_import_failure(reason) do
    raise Error.bundle_invalid("the catalog import was rolled back", %{
            "reason" => inspect(reason)
          })
  end
end
