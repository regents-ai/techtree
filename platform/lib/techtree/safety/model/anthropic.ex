defmodule Techtree.Safety.Model.Anthropic do
  @moduledoc """
  Model calls answered by Anthropic's Messages API.

  The key is read at boot from `TECHTREE_SAFETY_ANTHROPIC_API_KEY` in
  `config/runtime.exs`. Without it `available?/0` is false and the test page
  says comparisons are not switched on, rather than starting a run that would
  error on every case. The key is never printed.
  """

  @behaviour Techtree.Safety.Model

  @endpoint "https://api.anthropic.com/v1/messages"
  @model "claude-haiku-4-5-20251001"
  @max_tokens 800
  @receive_timeout 60_000

  @doc "The model every comparison on this site runs, named on the page that discloses it."
  @spec model() :: String.t()
  def model, do: @model

  @impl true
  def available?, do: is_binary(api_key()) and api_key() != ""

  @impl true
  def complete(system, user) when is_binary(system) and is_binary(user) do
    request =
      Req.new(
        url: @endpoint,
        headers: [
          {"x-api-key", api_key()},
          {"anthropic-version", "2023-06-01"}
        ],
        json: %{
          model: @model,
          max_tokens: @max_tokens,
          temperature: 0,
          system: system,
          messages: [%{role: "user", content: user}]
        },
        receive_timeout: @receive_timeout,
        retry: false
      )

    case Req.post(request) do
      {:ok, %Req.Response{status: 200, body: %{"content" => content}}} ->
        {:ok, content |> Enum.filter(&(&1["type"] == "text")) |> Enum.map_join("", & &1["text"])}

      {:ok, %Req.Response{status: status}} ->
        {:error, "the model provider answered with status #{status}"}

      {:error, exception} ->
        {:error, "the model provider could not be reached: #{Exception.message(exception)}"}
    end
  end

  defp api_key do
    :techtree
    |> Application.get_env(__MODULE__, [])
    |> Keyword.get(:api_key)
  end
end
