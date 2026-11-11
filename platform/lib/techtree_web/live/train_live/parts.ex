defmodule TechtreeWeb.TrainLive.Parts do
  @moduledoc """
  The pieces both Train pages draw: a comparison's figures and its strip of
  task results.
  """

  use TechtreeWeb, :html

  alias TechtreeWeb.TrainCopy, as: Copy

  @doc """
  Each arm's mean reward, then the difference between them in points.
  """
  attr :comparison, :map, required: true

  def figures(assigns) do
    ~H"""
    <dl class="train-figures">
      <div :for={arm <- @comparison.arms} class="train-figures__arm">
        <dt>{Copy.arm_label(@comparison, arm)}</dt>
        <dd>{Copy.percent(arm.mean_reward)}</dd>
      </div>
      <div class="train-figures__difference">
        <dt>Difference</dt>
        <dd>
          {Copy.points(@comparison.paired.mean_difference)}<span class="train-figures__unit">points</span>
        </dd>
      </div>
    </dl>
    """
  end

  @doc """
  One mark per task, the changed arm's wins first, then ties, then losses,
  read out as their counts.
  """
  attr :comparison, :map, required: true

  def strip(assigns) do
    assigns =
      assign(assigns,
        tasks: Enum.sort_by(assigns.comparison.tasks, &order(&1.result))
      )

    ~H"""
    <div class="train-strip" role="img" aria-label={"Tasks: " <> Copy.paired(@comparison.paired)}>
      <span
        :for={task <- @tasks}
        class={["train-strip__task", "train-strip__task--#{task.result}"]}
        title={"#{task.id}: #{Copy.result(task.result)}"}
      >
      </span>
    </div>
    """
  end

  @doc "A comparison's outcome as a status mark."
  attr :outcome, :atom, required: true
  attr :rest, :global

  def outcome(assigns) do
    ~H"""
    <Regent.Primitives.status tone={Copy.tone(@outcome)} class="badge" {@rest}>
      {Copy.outcome(@outcome)}
    </Regent.Primitives.status>
    """
  end

  defp order(:win), do: 0
  defp order(:tie), do: 1
  defp order(:loss), do: 2
end
