defmodule Techtree.WalletBench.Remote do
  @moduledoc """
  The bench's scripts on a machine (`priv/wallet_bench/machine/`), run through
  Sprites as the machine's owner account.

  A command that ends with a non-zero exit code is an error carrying the end of
  its error output; never its standard output, which may hold evidence that is
  not yet blanked. Long work (a baseline build, a harness turn) runs as a
  background job through `job.sh`, so no request has to stay open for it:
  starting a job twice only starts it once, and its status says whether it is
  running, finished with an exit code, or lost because the machine restarted.
  """

  @bin "/work/bin"
  @stderr_tail 2000

  @doc "Runs a command and returns what it printed, if it ended with exit code 0."
  @spec run(String.t(), [String.t(), ...], keyword()) :: {:ok, String.t()} | {:error, term()}
  def run(name, argv, opts \\ []) do
    case RegentSprites.exec(name, argv, opts) do
      {:ok, %RegentSprites.Output{exit_code: 0, stdout: stdout}} ->
        {:ok, stdout}

      {:ok, %RegentSprites.Output{exit_code: code, stderr: stderr}} ->
        {:error, "`#{Enum.join(argv, " ")}` ended with exit code #{code}: " <> tail(stderr)}

      {:error, error} ->
        {:error, error}
    end
  end

  @doc "Runs a bench script and decodes the JSON it printed."
  @spec json(String.t(), [String.t(), ...], keyword()) :: {:ok, term()} | {:error, term()}
  def json(name, argv, opts \\ []) do
    with {:ok, stdout} <- run(name, argv, opts) do
      Jason.decode(stdout)
    end
  end

  @doc "Unpacks a recipe pack into the machine's bench folder, readable by the owner only."
  @spec upload_pack(String.t(), binary()) :: :ok | {:error, term()}
  def upload_pack(name, pack) do
    script = "install -d -m 700 /work && install -d #{@bin} && tar -xzf - -C #{@bin}"

    with {:ok, _stdout} <-
           run(name, ["bash", "-c", script], stdin: pack, receive_timeout: 120_000) do
      :ok
    end
  end

  @doc """
  The digest of the scripts on the machine, made the way
  `Techtree.WalletBench.Catalog.recipe_digest/1` makes it from the pack.
  """
  @spec recipe_digest(String.t()) :: {:ok, String.t()} | {:error, term()}
  def recipe_digest(name) do
    script =
      "cd #{@bin} && find machine harness -type f -print0 | LC_ALL=C sort -z | " <>
        "xargs -0 sha256sum | sha256sum"

    with {:ok, stdout} <- run(name, ["bash", "-c", script]) do
      {:ok, stdout |> String.split() |> hd()}
    end
  end

  @doc "Starts a background job once; a job that already started is left alone."
  @spec start_job(String.t(), String.t(), [String.t(), ...]) :: :ok | {:error, term()}
  def start_job(name, job, argv) do
    with {:ok, _stdout} <- run(name, ["bash", "#{@bin}/machine/job.sh", "start", job | argv]) do
      :ok
    end
  end

  @doc """
  A background job's status. A new machine has no bench scripts until its
  recipe is uploaded, and so no job either.
  """
  @spec job_status(String.t(), String.t()) ::
          {:ok, :missing | :running | :lost | {:exit, non_neg_integer()}} | {:error, term()}
  def job_status(name, job) do
    script = ~s(if [ -f "$0" ]; then exec bash "$0" status "$1"; else echo missing; fi)

    with {:ok, stdout} <- run(name, ["sh", "-c", script, "#{@bin}/machine/job.sh", job]) do
      case String.trim(stdout) do
        "missing" -> {:ok, :missing}
        "running" -> {:ok, :running}
        "lost" -> {:ok, :lost}
        "exit " <> code -> {:ok, {:exit, String.to_integer(code)}}
      end
    end
  end

  @doc "The end of a background job's log."
  @spec job_log_tail(String.t(), String.t()) :: {:ok, String.t()} | {:error, term()}
  def job_log_tail(name, job) do
    with {:ok, log} <-
           run(name, ["tail", "-c", Integer.to_string(@stderr_tail), "/work/jobs/#{job}/log"]) do
      {:ok, String.replace_invalid(log)}
    end
  end

  defp tail(text) when byte_size(text) <= @stderr_tail, do: String.replace_invalid(text)

  defp tail(text),
    do:
      text
      |> binary_part(byte_size(text) - @stderr_tail, @stderr_tail)
      |> String.replace_invalid()
end
