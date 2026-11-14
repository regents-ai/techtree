defmodule Techtree.Projects.Manifest do
  @moduledoc """
  A package's `manifest.json`, format `uplift-package/1`: what the work found,
  written by the factory that ran it. Only the Skills line exists.

  It is checked strictly before anything is kept. Every object has exactly its
  keys, each named once; every value has its type; every count is a whole
  number from 0 to 1,000,000; every list holds at most 2,000 items; each
  solved count is at most its attempts, and each case's at most its repeats;
  every candidate is original, rewrite or skillopt. `files` names every other
  file in the package once, in path order, each inside the package's layout:
  `report.md`, `original/`, `selected/`, `cases/final/` and `rerun/`, with
  `report.md` and `rerun/README.md` always there. `Techtree.Projects.Package`
  checks the files themselves against it.

  A refusal names the first thing wrong by its place in the file, such as
  `summary.original.solved`.
  """

  @most 1_000_000
  @most_items 2_000
  @most_file_bytes 26_214_400
  @candidates ["original", "rewrite", "skillopt"]
  @folders ["original/", "selected/", "cases/final/", "rerun/"]
  @required_files ["report.md", "rerun/README.md"]

  @count {:whole, 0, @most}
  @positive {:whole, 1, @most}
  @candidate {:object,
              [
                {"candidate", {:one_of, @candidates}},
                {"solved", @count},
                {"attempts", @count},
                {"refused", :boolean},
                {"selected", :boolean}
              ]}

  @shape {:object,
          [
            {"schema", {:one_of, ["uplift-package/1"]}},
            {"line", {:one_of, ["skills"]}},
            {"title", {:name, 200}},
            {"job_id", :uuid},
            {"created_at", :utc_time},
            {"success", {:text, 2_000}},
            {"verdict", {:one_of, ["improved", "inconclusive", "not_improved"]}},
            {"summary",
             {:object,
              [
                {"repeats", @positive},
                {"final_cases", @positive},
                {"original", {:object, [{"solved", @count}, {"attempts", @positive}]}},
                {"selected",
                 {:object,
                  [
                    {"candidate", {:one_of, @candidates}},
                    {"solved", @count},
                    {"attempts", @positive}
                  ]}},
                {"difference", {:whole, -@most, @most}},
                {"p_value", {:nullable, :share}},
                {"pass_bar", :share},
                {"pass_bar_met", :boolean},
                {"regressions", @count},
                {"cost_cents", :decimal},
                {"attempts", @count},
                {"retries", @count}
              ]}},
            {"selection", {:list, @candidate}},
            {"cases",
             {:list,
              {:object,
               [
                 {"id", {:name, 200}},
                 {"original_solved", @count},
                 {"selected_solved", @count},
                 {"repeats", @positive}
               ]}}},
            {"setup",
             {:object,
              [
                {"model", {:name, 200}},
                {"tools",
                 {:list,
                  {:object,
                   [{"name", {:name, 100}}, {"maker", {:name, 100}}, {"version", {:name, 100}}]}}},
                {"limits", :limits},
                {"split",
                 {:object,
                  [
                    {"working", @count},
                    {"selection", @count},
                    {"final", @positive},
                    {"digest", :sha256}
                  ]}}
              ]}},
            {"files",
             {:list,
              {:object,
               [
                 {"path", :path},
                 {"sha256", :sha256},
                 {"size_bytes", {:whole, 0, @most_file_bytes}}
               ]}}}
          ]}

  @uuid ~r/\A[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\z/
  @sha256 ~r/\A[0-9a-f]{64}\z/
  @decimal ~r/\A(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\z/

  @doc "The manifest as a map with string keys, or what is wrong with it."
  @spec parse(binary()) :: {:ok, map()} | {:error, String.t()}
  def parse(json) do
    with {:ok, decoded} <- decode(json),
         {:ok, manifest} <- plain(decoded),
         :ok <- check(manifest, @shape, []),
         :ok <- within_attempts(manifest),
         :ok <- files_in_layout(manifest["files"]) do
      {:ok, manifest}
    end
  end

  @doc "A checked manifest's service line, as a project keeps it."
  @spec line(map()) :: :skills
  def line(%{"line" => "skills"}), do: :skills

  @doc "A checked manifest's verdict, as a project keeps it."
  @spec verdict(map()) :: :improved | :inconclusive | :not_improved
  def verdict(%{"verdict" => "improved"}), do: :improved
  def verdict(%{"verdict" => "inconclusive"}), do: :inconclusive
  def verdict(%{"verdict" => "not_improved"}), do: :not_improved

  defp decode(json) do
    case Jason.decode(json, objects: :ordered_objects) do
      {:ok, decoded} -> {:ok, decoded}
      {:error, _error} -> {:error, "manifest.json isn't valid JSON."}
    end
  end

  # Objects become maps once each key is known to appear only once in them.
  defp plain(%Jason.OrderedObject{values: pairs}) do
    Enum.reduce_while(pairs, {:ok, %{}}, fn {key, value}, {:ok, map} ->
      with false <- Map.has_key?(map, key),
           {:ok, value} <- plain(value) do
        {:cont, {:ok, Map.put(map, key, value)}}
      else
        true -> {:halt, {:error, "manifest.json names #{key} twice in one object."}}
        error -> {:halt, error}
      end
    end)
  end

  defp plain(list) when is_list(list) do
    Enum.reduce_while(list, {:ok, []}, fn value, {:ok, values} ->
      case plain(value) do
        {:ok, value} -> {:cont, {:ok, [value | values]}}
        error -> {:halt, error}
      end
    end)
    |> case do
      {:ok, values} -> {:ok, Enum.reverse(values)}
      error -> error
    end
  end

  defp plain(value), do: {:ok, value}

  defp check(value, {:object, fields}, at) when is_map(value) do
    keys = Enum.map(fields, &elem(&1, 0))

    cond do
      extra = value |> Map.keys() |> Enum.sort() |> Enum.find(&(&1 not in keys)) ->
        {:error, "In manifest.json, #{place(at ++ [extra])} isn't part of the format."}

      missing = Enum.find(keys, &(not Map.has_key?(value, &1))) ->
        {:error, "In manifest.json, #{place(at ++ [missing])} is missing."}

      true ->
        each(fields, fn {key, shape} -> check(Map.fetch!(value, key), shape, at ++ [key]) end)
    end
  end

  defp check(value, {:list, shape}, at) when is_list(value) and length(value) <= @most_items do
    value
    |> Enum.with_index()
    |> each(fn {item, index} -> check(item, shape, at ++ [index]) end)
  end

  defp check(value, {:nullable, _shape}, _at) when is_nil(value), do: :ok
  defp check(value, {:nullable, shape}, at), do: check(value, shape, at)

  defp check(value, {:whole, least, most}, _at)
       when is_integer(value) and value >= least and value <= most,
       do: :ok

  defp check(value, :share, _at) when is_number(value) and value >= 0 and value <= 1, do: :ok
  defp check(value, :boolean, _at) when is_boolean(value), do: :ok

  defp check(value, {:one_of, values}, at) when is_binary(value),
    do: if(value in values, do: :ok, else: wrong(at, {:one_of, values}))

  defp check(value, {:name, most}, at) when is_binary(value),
    do: text(value, most, RegentFormat.Name.pattern(), at, {:name, most})

  defp check(value, {:text, most}, at) when is_binary(value),
    do: text(value, most, RegentFormat.Text.pattern(), at, {:text, most})

  defp check(value, :uuid, at) when is_binary(value), do: matches(value, @uuid, at, :uuid)
  defp check(value, :sha256, at) when is_binary(value), do: matches(value, @sha256, at, :sha256)

  defp check(value, :decimal, at) when is_binary(value),
    do: matches(value, @decimal, at, :decimal)

  defp check(value, :utc_time, at) when is_binary(value) do
    case DateTime.from_iso8601(value) do
      {:ok, _time, 0} -> :ok
      _other -> wrong(at, :utc_time)
    end
  end

  defp check(value, :path, at) when is_binary(value) do
    if path?(value), do: :ok, else: wrong(at, :path)
  end

  defp check(value, :limits, at) when is_map(value) and map_size(value) <= 100 do
    value
    |> Enum.sort()
    |> each(fn {key, setting} ->
      with :ok <- check(key, {:name, 100}, at ++ [key]) do
        limit(setting, at ++ [key])
      end
    end)
  end

  defp check(_value, shape, at), do: wrong(at, shape)

  defp limit(setting, _at) when is_number(setting), do: :ok
  defp limit(setting, at) when is_binary(setting), do: check(setting, {:name, 200}, at)
  defp limit(_setting, at), do: wrong(at, :limit)

  defp text(value, most, pattern, at, shape) do
    if value != "" and String.length(value) <= most and Regex.match?(pattern, value),
      do: :ok,
      else: wrong(at, shape)
  end

  defp matches(value, pattern, at, shape),
    do: if(Regex.match?(pattern, value), do: :ok, else: wrong(at, shape))

  # A path inside the package: relative, each part named, none of them `.` or `..`.
  defp path?(value) do
    byte_size(value) <= 255 and Regex.match?(RegentFormat.Name.pattern(), value) and
      not String.contains?(value, "\\") and
      value |> String.split("/") |> Enum.all?(&(&1 not in ["", ".", ".."]))
  end

  defp within_attempts(manifest) do
    summary = manifest["summary"]

    counts =
      [
        {["summary", "original"], summary["original"]},
        {["summary", "selected"], summary["selected"]}
      ] ++ Enum.with_index(manifest["selection"], &{["selection", &2], &1})

    with :ok <- each(counts, &solved_within_attempts/1) do
      manifest["cases"]
      |> Enum.with_index(&{["cases", &2], &1})
      |> each(&solved_within_repeats/1)
    end
  end

  defp solved_within_attempts({at, %{"solved" => solved, "attempts" => attempts}}) do
    if solved <= attempts,
      do: :ok,
      else: {:error, "In manifest.json, #{place(at)} solved more than its attempts."}
  end

  defp solved_within_repeats({at, item}) do
    if max(item["original_solved"], item["selected_solved"]) <= item["repeats"],
      do: :ok,
      else: {:error, "In manifest.json, #{place(at)} solved more than its repeats."}
  end

  defp files_in_layout(files) do
    paths = Enum.map(files, & &1["path"])

    cond do
      paths != Enum.sort(Enum.uniq(paths)) ->
        {:error, "In manifest.json, files must be in path order, each path once."}

      outside = Enum.find(paths, &(&1 != "report.md" and not String.starts_with?(&1, @folders))) ->
        {:error,
         "In manifest.json, files lists #{outside}, which is outside the package's layout."}

      missing = Enum.find(@required_files, &(&1 not in paths)) ->
        {:error, "In manifest.json, files doesn't list #{missing}."}

      true ->
        :ok
    end
  end

  defp each(items, check) do
    Enum.reduce_while(items, :ok, fn item, :ok ->
      case check.(item) do
        :ok -> {:cont, :ok}
        error -> {:halt, error}
      end
    end)
  end

  defp wrong(at, shape),
    do: {:error, "In manifest.json, #{place(at)} should be #{expected(shape)}."}

  defp expected({:object, fields}),
    do: "an object with " <> Enum.map_join(fields, ", ", &elem(&1, 0))

  defp expected({:list, _shape}), do: "a list of at most 2,000 items"
  defp expected({:nullable, shape}), do: expected(shape) <> ", or null"

  defp expected({:whole, least, most}),
    do: "a whole number from #{delimited(least)} to #{delimited(most)}"

  defp expected(:share), do: "a number from 0 to 1"
  defp expected(:boolean), do: "true or false"
  defp expected({:one_of, [value]}), do: ~s("#{value}")
  defp expected({:one_of, values}), do: "one of " <> Enum.map_join(values, ", ", &~s("#{&1}"))

  defp expected({kind, most}) when kind in [:name, :text],
    do: "text of 1 to #{delimited(most)} characters, with no hidden characters"

  defp expected(:uuid), do: "a lowercase UUID"
  defp expected(:sha256), do: "a sha256 in 64 lowercase hex digits"
  defp expected(:decimal), do: ~s(a decimal number written as text, such as "1250.5")
  defp expected(:utc_time), do: "an ISO 8601 time in UTC"
  defp expected(:path), do: "a path inside the package, such as original/SKILL.md"
  defp expected(:limits), do: "an object of at most 100 settings"
  defp expected(:limit), do: "text or a number"

  defp delimited(number), do: RegentFormat.add_delimiters(Integer.to_string(number))

  defp place([]), do: "the file"

  defp place(at) do
    Enum.reduce(at, "", fn
      index, place when is_integer(index) -> place <> "[#{index}]"
      key, "" -> key
      key, place -> place <> "." <> key
    end)
  end
end
