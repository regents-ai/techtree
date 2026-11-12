defmodule TechtreeWeb.VisitLinesTest do
  # Invariant: a crowd's second of visit lines, 1,500 written at once, reaches the
  # site's output whole, each line once; and an ordinary line is written once, by
  # the default handler.
  use ExUnit.Case, async: false

  require Logger

  alias TechtreeWeb.VisitLog

  @crowd 1_500

  @tag :tmp_dir
  test "1,500 visit lines in one second are all written, once each", %{tmp_dir: dir} do
    files = write_to_files(dir)

    {microseconds, _lines} =
      :timer.tc(fn ->
        1..@crowd
        |> Enum.map(fn _ ->
          Task.async(fn -> VisitLog.record("press", "Crowd:press", "ok") end)
        end)
        |> Task.await_many()
      end)

    Logger.info("an ordinary line")
    lines = read(files)

    assert microseconds < 1_000_000
    assert Enum.count(lines.all, &(&1["message"] == "press Crowd:press ok")) == @crowd
    assert Enum.count(lines.all, &(&1["message"] == "an ordinary line")) == 1
    assert Enum.count(lines.default, &(&1["message"] == "an ordinary line")) == 1
  end

  # The site's own handlers, each copied to write production's lines to a file in
  # place of standard output while the originals stay quiet.
  defp write_to_files(dir) do
    level = Logger.level()
    json = LoggerJSON.Formatters.Basic.new(metadata: VisitLog.fields())

    files =
      for id <- :logger.get_handler_ids(),
          {:ok, handler} = :logger.get_handler_config(id),
          handler.module == :logger_std_h,
          handler.config.type == :standard_io do
        copy = :"#{id}_to_file"
        file = Path.join(dir, "#{id}.jsonl")
        config = handler.config |> Map.delete(:type) |> Map.put(:file, String.to_charlist(file))

        :ok =
          :logger.add_handler(copy, :logger_std_h, %{
            handler
            | id: copy,
              config: config,
              formatter: json
          })

        :ok = :logger.update_handler_config(id, :level, :none)

        on_exit(fn ->
          :logger.remove_handler(copy)
          :logger.update_handler_config(id, :level, handler.level)
        end)

        {id, copy, file}
      end

    Logger.configure(level: :info)
    on_exit(fn -> Logger.configure(level: level) end)
    files
  end

  defp read(files) do
    by_handler =
      Map.new(files, fn {id, copy, file} ->
        :ok = :logger_std_h.filesync(copy)
        {id, file |> File.read!() |> String.split("\n", trim: true) |> Enum.map(&JSON.decode!/1)}
      end)

    %{all: by_handler |> Map.values() |> List.flatten(), default: by_handler.default}
  end
end
