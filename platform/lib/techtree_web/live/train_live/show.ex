defmodule TechtreeWeb.TrainLive.Show do
  @moduledoc """
  One comparison, reached from Results and the home page's demonstrations: the
  Skill with its links, the task, the original and improved Skill's attempts
  solved on the final test as two bars with the verdict, the method with the
  choosing step's figures, every final-test case, the tools, and the report to
  download.

  The comparison is one committed file (`Techtree.Train.Comparisons`); a slug
  the folder has no file for is a 404.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Train.Comparisons
  alias TechtreeWeb.TrainCopy, as: Copy

  @impl true
  def mount(%{"slug" => slug}, _session, socket) do
    case Comparisons.fetch(slug) do
      {:ok, comparison} ->
        {:ok, assign(socket, page_title: comparison.skill.name, comparison: comparison)}

      :error ->
        raise TechtreeWeb.NotFoundError, "no comparison has that name"
    end
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <div class="train">
        <p class="back-link"><.link navigate={~p"/results"}>← Results</.link></p>

        <header class="page-heading">
          <p class="eyebrow">Demonstration · {Copy.date(@comparison.date)}</p>
          <h1>{@comparison.skill.name}</h1>
          <p class="lede">{@comparison.skill.summary}</p>
          <p class="train-provenance">{Copy.provenance(@comparison)}</p>
          <p class="mk-links">
            <a href={@comparison.skill.github_url} class="text-link" rel="noopener">
              GitHub <span aria-hidden="true">↗</span>
            </a>
            <a href={@comparison.skill.skills_sh_url} class="text-link" rel="noopener">
              skills.sh <span aria-hidden="true">↗</span>
            </a>
          </p>
        </header>

        <section id="task" class="section" aria-labelledby="task-title">
          <h2 id="task-title">Task</h2>
          <p class="train-reading">{@comparison.task}</p>
        </section>

        <section id="result" class="train-lead" aria-labelledby="result-title">
          <h2 id="result-title">Result</h2>
          <p class="train-note">{Copy.final_test(@comparison)}</p>
          <div class="train-bars">
            <.bar id="result-original" label="Original" side={@comparison.final.original} />
            <.bar
              id="result-improved"
              label="Revised"
              side={@comparison.final.improved}
              improved
            />
          </div>
          <dl class="train-facts">
            <div id="result-verdict" data-verdict={@comparison.verdict}>
              <dt>Verdict</dt>
              <dd>{Copy.verdict_name(@comparison)}</dd>
            </div>
            <div>
              <dt>Difference</dt>
              <dd>{Copy.difference(@comparison)}</dd>
            </div>
            <div>
              <dt>Cases</dt>
              <dd>{Copy.changes(@comparison)}</dd>
            </div>
            <div>
              <dt>Chance</dt>
              <dd>{Copy.odds(@comparison)}</dd>
            </div>
          </dl>
          <p class="train-note">{Copy.verdict(@comparison)} {Copy.chance(@comparison)}</p>
        </section>

        <section id="method" class="section" aria-labelledby="method-title">
          <h2 id="method-title">Method</h2>
          <ol class="train-steps">
            <li :for={{title, words, choices} <- Copy.method(@comparison)}>
              <h3>{title}</h3>
              <p>{words}</p>
              <div
                :if={choices != []}
                id="choosing"
                class="train-bars train-bars--small"
                role="group"
                aria-label={title}
              >
                <.bar
                  :for={{name, side, chosen} <- choices}
                  id={"choosing-#{String.downcase(name)}"}
                  label={name}
                  side={side}
                  improved={chosen}
                />
              </div>
            </li>
          </ol>
        </section>

        <section id="cases" class="section" aria-labelledby="cases-title">
          <h2 id="cases-title">Cases</h2>
          <p class="train-reading">{Copy.worse(@comparison)}</p>
          <div class="train-table" role="region" aria-labelledby="cases-title" tabindex="0">
            <table>
              <thead>
                <tr>
                  <th scope="col">Case</th>
                  <th scope="col">Original</th>
                  <th scope="col">Revised</th>
                  <th scope="col">Change</th>
                </tr>
              </thead>
              <tbody>
                <tr :for={item <- @comparison.cases} id={"case-#{item.id}"} data-change={item.change}>
                  <th scope="row"><bdi>{item.id}</bdi></th>
                  <td>{Copy.solved(item.original, @comparison.repeats)}</td>
                  <td>{Copy.solved(item.improved, @comparison.repeats)}</td>
                  <td>
                    <span class={"train-change train-change--#{item.change}"}>
                      {Copy.change(item)}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section id="tools" class="section" aria-labelledby="tools-title">
          <h2 id="tools-title">Tools</h2>
          <dl class="train-tools">
            <div :for={{term, words} <- Copy.tools(@comparison)}>
              <dt>{term}</dt>
              <dd>{words}</dd>
            </div>
          </dl>
        </section>

        <section id="report" class="section" aria-labelledby="report-title">
          <h2 id="report-title">Report</h2>
          <p class="train-reading">
            The report lists every final-test case with the attempts each version solved, so the
            figures above can be counted again from it.
          </p>
          <div class="train-downloads">
            <a
              class="rg-button rg-button--primary rg-button--no-arrow"
              href={~p"/train/#{@comparison.slug}/report.json"}
              download={"#{@comparison.slug}.json"}
            >
              <Regent.Icons.icon name="download" /> Report
            </a>
          </div>
          <p class="mk-links">
            <.link
              navigate={~p"/docs/verify" <> "#blog-section-skill-comparisons"}
              class="text-link"
            >
              How to check it <span aria-hidden="true">→</span>
            </.link>
          </p>
        </section>
      </div>
    </Layouts.page>
    """
  end

  attr :id, :string, required: true
  attr :label, :string, required: true
  attr :side, :map, required: true
  attr :improved, :boolean, default: false

  # One version's row: its name, a bar whose fill is the share of attempts
  # solved, and the figure as text.
  defp bar(assigns) do
    ~H"""
    <div id={@id} class={["train-bar", @improved && "train-bar--improved"]}>
      <span class="train-bar__label">{@label}</span>
      <span class="train-bar__track" aria-hidden="true">
        <span
          class="train-bar__fill"
          style={"inline-size: #{@side.solved * 100 / @side.attempts}%"}
        ></span>
      </span>
      <span class="train-bar__figure">
        <span class="train-bar__percent">{Copy.percent(@side)}</span>
        <span class="train-bar__count">{Copy.count(@side)}</span>
      </span>
    </div>
    """
  end
end
