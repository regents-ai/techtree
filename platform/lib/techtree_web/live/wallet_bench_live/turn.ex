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
          <dd>{Copy.version(version)}</dd>
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

  attr :ruling, :map, required: true
  attr :test, :atom, required: true, doc: "the grid test the ruling is for"
  attr :rest, :global

  @doc "A grid test's score out of 10, its outcome, and why it is under 10."
  def verdict(assigns) do
    assigns =
      assign(assigns,
        score: Copy.score(assigns.ruling),
        shortfall: Copy.shortfall(assigns.ruling, assigns.test)
      )

    ~H"""
    <div class="wallet-bench__verdict" {@rest}>
      <span class={[
        "wallet-bench__score",
        "wallet-bench__score--#{Copy.shade(@score)}",
        @ruling["outcome"] == "FAILED_SAFETY" && "wallet-bench__score--safety"
      ]}>
        {@score}
      </span>
      <div>
        <p>
          <strong>{Copy.grid_test_name(@test)}: {@score} out of 10.</strong>
          {Copy.outcome(@ruling)}. {Copy.checks_met(@ruling)} of {map_size(@ruling["criteria"])} checks met.
        </p>
        <ul :if={@shortfall != []} class="wallet-bench__shortfall">
          <li :for={reason <- @shortfall}>{reason}</li>
        </ul>
      </div>
    </div>
    """
  end

  @doc "Whether the judge ruled on a turn; the last turn of a money attempt is the bench's own check."
  @spec scored?(map()) :: boolean()
  def scored?(turn), do: turn.judgment != nil and turn.judgment["outcome"] != "UNSCORED"
end
