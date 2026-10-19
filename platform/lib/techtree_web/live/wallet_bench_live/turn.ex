defmodule TechtreeWeb.WalletBenchLive.Turn do
  @moduledoc """
  One test of a wallet test attempt: its ruling with each check and its reason,
  the bench's own checks, what it took and cost, the prompt it was sent and the
  files it recorded. The test's own page shows every test this way, and the
  grid's result window shows the tests of the column picked.
  """

  use TechtreeWeb, :html

  alias Techtree.WalletBench.Catalog
  alias TechtreeWeb.WalletBenchCopy, as: Copy

  attr :attempt_id, :string, required: true
  attr :turn, :map, required: true
  attr :level, :integer, default: 2, doc: "the heading level of the test's name"
  attr :id_prefix, :string, default: "test"

  def turn(assigns) do
    ~H"""
    <section
      id={"#{@id_prefix}-#{Catalog.turn_name(@turn.test)}"}
      class={["wallet-bench__test", "wallet-bench__test--#{Copy.tone(@turn.judgment)}"]}
      aria-labelledby={"#{@id_prefix}-#{Catalog.turn_name(@turn.test)}-title"}
    >
      <.dynamic_tag
        tag_name={"h#{@level}"}
        id={"#{@id_prefix}-#{Catalog.turn_name(@turn.test)}-title"}
      >
        {Copy.test(@turn.test)}
      </.dynamic_tag>
      <p class="wallet-bench__outcome">
        <strong>{if @turn.judgment,
          do: Copy.outcome(@turn.judgment),
          else: Copy.turn_state(@turn.state)}</strong>
      </p>
      <p :if={@turn.failure} class="wallet-bench__failure">{@turn.failure}</p>

      <%= if @turn.judgment do %>
        <p>{@turn.judgment["summary"]}</p>

        <table :if={@turn.judgment["criteria"]} class="results-ledger wallet-bench__criteria">
          <caption class="offscreen">The judge's checks</caption>
          <thead>
            <tr>
              <th scope="col">Check</th>
              <th scope="col">Answer</th>
              <th scope="col">Why</th>
            </tr>
          </thead>
          <tbody>
            <tr :for={key <- @turn.judgment["criteria"] |> Map.keys() |> Enum.sort()}>
              <th scope="row">{Copy.criterion_question(@turn.test, key)}</th>
              <td class="wallet-bench__value">
                {Copy.criterion(@turn.judgment["criteria"][key]["value"])}
              </td>
              <td>{@turn.judgment["criteria"][key]["reason"]}</td>
            </tr>
          </tbody>
        </table>

        <details :if={@turn.judgment["reasoning"]} class="wallet-bench__reasoning">
          <summary>The judge's reasoning</summary>
          <p>{@turn.judgment["reasoning"]}</p>
        </details>
      <% end %>

      <dl class="wallet-bench__facts">
        <%= if @turn.test == :T2 do %>
          <dt>Question asked</dt>
          <dd>{Copy.question_wording(@turn.prompt)}</dd>
        <% end %>
        <%= if version = @turn.checks["version"] do %>
          <dt>Version installed</dt>
          <dd>
            {if version["installed"] in ["", nil], do: "Not shown", else: version["installed"]}{version_note(
              version
            )}
          </dd>
        <% end %>
        <%= if base = Copy.base(@turn.checks["base"]) do %>
          <dt>The bench's Base check</dt>
          <dd>{base}</dd>
        <% end %>
        <%= if money = Copy.money(@turn.checks["money"]) do %>
          <dt>The bench's Base check</dt>
          <dd>{money}</dd>
        <% end %>
        <dt :if={@turn.wall_seconds}>Time taken</dt>
        <dd :if={@turn.wall_seconds}>
          {@turn.wall_seconds} seconds of {Catalog.wall_cap(@turn.test)}
        </dd>
        <dt :if={@turn.model_spend_usd}>Model cost</dt>
        <dd :if={@turn.model_spend_usd}>{Copy.dollars(@turn.model_spend_usd)}</dd>
        <dt :if={scored?(@turn)}>Judged by</dt>
        <dd :if={scored?(@turn)}>{@turn.judgment["model"]}</dd>
        <dt :if={@turn.judge_cost_usd}>Judge cost</dt>
        <dd :if={@turn.judge_cost_usd}>{Copy.dollars(@turn.judge_cost_usd)}</dd>
      </dl>

      <details class="wallet-bench__files">
        <summary>The prompt sent</summary>
        <pre>{@turn.prompt}</pre>
      </details>

      <div :if={@turn.evidence} class="wallet-bench__files">
        <.dynamic_tag tag_name={"h#{@level + 1}"}>Recorded files</.dynamic_tag>
        <p class="quiet">Secrets were blanked before anything was stored.</p>
        <ul>
          <li :for={{file, %{"bytes" => bytes}} <- Enum.sort(@turn.evidence)}>
            <a href={
              ~p"/wallet-bench/#{@attempt_id}/evidence/#{Catalog.turn_name(@turn.test)}/#{file}"
            }>
              {file}
            </a>
            <span class="quiet">{bytes} bytes</span>
          </li>
        </ul>
      </div>
    </section>
    """
  end

  @doc "Whether the judge ruled on a turn; the last turn of a money attempt is the bench's own check."
  @spec scored?(map()) :: boolean()
  def scored?(turn), do: turn.judgment != nil and turn.judgment["outcome"] != "UNSCORED"

  defp version_note(%{"matches_requested" => true}), do: ", the release this run asked for."

  defp version_note(%{"matches_requested" => false, "requested" => requested}),
    do: ", not the #{requested} this run asked for."

  defp version_note(%{"matches_survey" => true}), do: ", the same as the survey."

  defp version_note(%{"matches_survey" => false, "survey" => survey}),
    do: ", not the #{survey} the survey installed."

  defp version_note(%{"matches_survey" => nil}), do: "."
end
