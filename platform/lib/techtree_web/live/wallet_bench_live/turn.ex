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
      <div
        :if={@turn.judgment}
        class={["wallet-bench__finding", "wallet-bench__finding--#{Copy.tone(@turn.judgment)}"]}
      >
        <p class="wallet-bench__finding-title">
          <Regent.Icons.icon name={Copy.outcome_icon(@turn.judgment)} />
          <strong>{Copy.outcome(@turn.judgment)}</strong>
        </p>
        <p>{@turn.judgment["summary"]}</p>
        <p :if={Copy.safety_outside_checks?(@turn.judgment)} class="wallet-bench__finding-note">
          {Copy.outside_checks(@turn.judgment)}
        </p>
      </div>
      <p :if={!@turn.judgment} class="wallet-bench__outcome">
        <strong>{Copy.turn_state(@turn.state)}</strong>
      </p>
      <p :if={@turn.failure} class="wallet-bench__failure">{@turn.failure}</p>

      <%= if @turn.judgment do %>
        <table :if={@turn.judgment["criteria"]} class="results-ledger wallet-bench__criteria">
          <caption class="offscreen">Judge checks</caption>
          <thead>
            <tr>
              <th scope="col">Check</th>
              <th scope="col">Answer</th>
              <th scope="col">Why</th>
            </tr>
          </thead>
          <tbody>
            <.check
              :for={key <- @turn.judgment["criteria"] |> Map.keys() |> Enum.sort()}
              question={Copy.criterion_question(@turn.test, key)}
              check={@turn.judgment["criteria"][key]}
            />
          </tbody>
        </table>

        <details :if={@turn.judgment["reasoning"]} class="wallet-bench__reasoning">
          <summary>Reasoning</summary>
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
          <dt>Base check</dt>
          <dd>{base}</dd>
        <% end %>
        <%= if money = Copy.money(@turn.checks["money"]) do %>
          <dt>Base check</dt>
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
        <summary>Prompt</summary>
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

  attr :question, :string, required: true
  attr :check, :map, required: true, doc: "the judge's answer to one check, with its reason"

  # One of the judge's checks: a check not met stands out as a row, and every
  # answer carries its mark beside its word.
  defp check(assigns) do
    {state, icon} = Copy.answer_mark(assigns.check["value"])
    assigns = assign(assigns, state: state, icon: icon)

    ~H"""
    <tr class={"wallet-bench__check wallet-bench__check--#{@state}"}>
      <th scope="row">{@question}</th>
      <td class="wallet-bench__value">
        <span class="wallet-bench__answer">
          <Regent.Icons.icon name={@icon} />{Copy.criterion(@check["value"])}
        </span>
      </td>
      <td>{@check["reason"]}</td>
    </tr>
    """
  end

  attr :turn, :map, required: true, doc: "the turn whose ruling is the grid test's result"
  attr :test, :atom, required: true, doc: "the grid test the ruling is for"

  attr :id_prefix, :string,
    default: "test",
    doc: "the id prefix of the turn's section, as `turn/1` takes"

  attr :rest, :global

  @doc """
  A grid test's score out of 10, its outcome, and why it is under 10, its
  title linking to the section of the turn it describes.
  """
  def verdict(assigns) do
    ruling = assigns.turn.judgment
    score = Copy.score(ruling)

    assigns =
      assign(assigns,
        ruling: ruling,
        score: score,
        title: "#{Copy.grid_test_name(assigns.test)}: #{score} out of 10.",
        href: "##{assigns.id_prefix}-#{Catalog.turn_name(assigns.turn.test)}",
        shortfall: Copy.shortfall(ruling, assigns.test)
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
          <a href={@href}>{@title}</a>
          {Copy.verdict_line(@ruling)}
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
