defmodule TechtreeWeb.Telemetry.Buckets do
  @moduledoc """
  Histogram buckets for the site's distributions, as the Prometheus format
  defines them: a bucket counts every observation less than or equal to its
  bound. Each distribution lists its bounds in `reporter_options` as `buckets:`.

  Peep's own `Peep.Buckets.Custom` puts an observation equal to a bound in the
  bucket above it. With whole-number units an observation lands exactly on a
  bound often (a query that waited 1,000 microseconds), so that would count it
  in the wrong bucket.
  """

  @behaviour Peep.Buckets

  @impl true
  def config(%Telemetry.Metrics.Distribution{reporter_options: options}),
    do: %{bounds: options |> Keyword.fetch!(:buckets) |> Enum.sort() |> List.to_tuple()}

  @impl true
  def number_of_buckets(%{bounds: bounds}), do: tuple_size(bounds)

  @impl true
  def bucket_for(value, %{bounds: bounds}), do: index(value, bounds, 0)

  # Peep's export reads each bound back as a float.
  @impl true
  def upper_bound(index, %{bounds: bounds}) when index < tuple_size(bounds),
    do: Float.to_string(elem(bounds, index) * 1.0)

  def upper_bound(_above_every_bound, _config), do: "+Inf"

  defp index(_value, bounds, index) when index == tuple_size(bounds), do: index
  defp index(value, bounds, index) when value <= elem(bounds, index), do: index
  defp index(value, bounds, index), do: index(value, bounds, index + 1)
end
