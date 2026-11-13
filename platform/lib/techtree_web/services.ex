defmodule TechtreeWeb.Services do
  @moduledoc """
  What Techtree sells: four services built around a customer's own workflows
  (Skills, Evals, Environments and Models), and Security beside them. Each is
  a paid custom project, delivered by people.

  Each service is one map: its name, a Lucide icon, a short line for the
  menus, its promise, its price level (1 to 4, shown as marks and never as a
  figure), what the customer brings, what we do, what they receive and the
  line that asks for a call. Security has no price level. The header's Services menu
  (`TechtreeWeb.SiteMenu`), the home page's cards, each service's page
  (`TechtreeWeb.ServiceLive`) and its Markdown all read them from here, so they
  never say different things. A new fact about a service is one more key.

  A step of the work is a list of words and links: a link is `{text, href}`
  and names another company's open-source project as one we use on a project,
  never as part of Techtree.
  """

  use TechtreeWeb, :verified_routes

  @type words :: [String.t() | {String.t(), String.t()}]
  @type service :: %{
          id: atom(),
          name: String.t(),
          icon: String.t(),
          line: String.t(),
          promise: String.t(),
          price: 1..4,
          call: String.t(),
          bring: [String.t()],
          work: [words()],
          receive: [String.t()],
          note: String.t() | nil
        }
  @type option :: %{
          id: String.t(),
          name: String.t(),
          line: String.t(),
          items: [String.t()],
          link: {String.t(), String.t()}
        }
  @type security :: %{
          id: :security,
          name: String.t(),
          icon: String.t(),
          line: String.t(),
          promise: String.t(),
          call: String.t(),
          options: [option()],
          rules: [String.t()]
        }

  @skill_evaluator {"NVIDIA’s SkillEvaluator", "https://github.com/NVIDIA/SkillEvaluator"}
  @skill_opt {"Microsoft’s SkillOpt", "https://github.com/microsoft/SkillOpt"}
  @verifiers {"Prime Intellect’s Verifiers", "https://github.com/PrimeIntellect-ai/verifiers"}
  @prime_rl {"Prime Intellect’s prime-rl", "https://github.com/PrimeIntellect-ai/prime-rl"}
  @skill2env {"NVIDIA’s Skill2Env", "https://github.com/NVlabs/Skill2Env"}
  @repo2rlenv {"Hugging Face’s Repo2RLEnv", "https://github.com/huggingface/Repo2RLEnv"}

  @doc "The four services, in the order every list shows them."
  @spec all() :: [service()]
  def all do
    [
      %{
        id: :skills,
        name: "Skills",
        icon: "wand-sparkles",
        line: "Improve how an agent works",
        promise: "Improve how an existing agent handles a particular workflow.",
        price: 1,
        call:
          "Bring the Skill and a few examples of good and bad work. We’ll agree what better means before anything changes.",
        bring: [
          "An existing Skill.",
          "The agent and the model that use it.",
          "Examples of work it got right, and work it got wrong."
        ],
        work: [
          [
            "We use ",
            @skill_evaluator,
            " to diagnose the Skill’s quality and measure how the agent behaves with it."
          ],
          [
            "We use ",
            @skill_opt,
            " to propose changes to its instructions from scored attempts."
          ],
          [
            "We run the final comparison on cases the work never saw, keeping the model, tools and budgets fixed."
          ]
        ],
        receive: [
          "The revised Skill.",
          "Instructions to install it.",
          "A report on success, cost and regressions."
        ],
        note: nil
      },
      %{
        id: :evals,
        name: "Evals",
        icon: "clipboard-check",
        line: "Test whether agents can do the job",
        promise: "Build a reliable test for whether agents can do this job.",
        price: 2,
        call:
          "Bring the workflow and a few examples. We’ll agree what success means before we write a test.",
        bring: [
          "A workflow and representative examples.",
          "The failures you already know about.",
          "Your definition of success.",
          "Or an existing eval to improve."
        ],
        work: [
          ["We use ", @verifiers, " to define the tasks and score them."],
          ["We use ", @prime_rl, " to run the evaluation."],
          ["Where a task needs a working software environment, we package it with Harbor."]
        ],
        receive: [
          "Reviewed test cases.",
          "Graders.",
          "Baseline results.",
          "An analysis of the failures.",
          "One command that reruns the suite."
        ],
        note:
          "A better eval catches the failures that matter and scores the same work the same way every time. It need not produce a higher pass rate."
      },
      %{
        id: :environments,
        name: "Environments",
        icon: "boxes",
        line: "Practice for agents on your work",
        promise: "Turn your workflow into repeatable practice for agents.",
        price: 3,
        call:
          "Bring the workflow, the Skill or the repository. We’ll agree which tasks the environment should hold.",
        bring: [
          "A Skill, a repository, or a description of your workflow and its tools.",
          "Or an existing Harbor, Prime or OpenEnv environment."
        ],
        work: [
          ["We use ", @skill2env, " to generate Harbor tasks from a Skill."],
          [
            "We use ",
            @repo2rlenv,
            " to generate them from a repository, its past fixes and recorded agent sessions."
          ],
          ["We use ", @verifiers, " to run the tasks and score them."],
          [
            "We make sure the environment represents your actual job, and check that its tests accept good work and reject bad work."
          ]
        ],
        receive: [
          "A resettable environment.",
          "Realistic tasks, with their tools and fixtures.",
          "Reference solutions.",
          "Scoring.",
          "Entry points for evaluation and training."
        ],
        note: nil
      },
      %{
        id: :models,
        name: "Models",
        icon: "brain-circuit",
        line: "Train an open-weight model",
        promise: "Train an open-weight model for the workflows that matter to your business.",
        price: 4,
        call:
          "Bring the workflow and the base model you have in mind. We’ll agree the baseline and the final test first.",
        bring: [
          "A supported base model.",
          "Examples of the work.",
          "A validated training environment.",
          "An independent eval."
        ],
        work: [
          [
            "We use ",
            @prime_rl,
            " for supervised fine-tuning and reinforcement learning, on tasks defined with Prime Intellect’s Verifiers."
          ],
          ["We choose the method after measuring the baseline."]
        ],
        receive: [
          "A checkpoint or adapter.",
          "The training recipe.",
          "A deployment handover.",
          "A comparison with the original model, including the cost per successful task."
        ],
        note: nil
      }
    ]
  end

  @doc "Security, offered beside the four: a one-off review or a monthly watch."
  @spec security() :: security()
  def security do
    %{
      id: :security,
      name: "Security",
      icon: "shield-check",
      line: "Review or watch what you run",
      promise: "Find and fix the security weaknesses that matter, once or every month.",
      call:
        "Tell us what you want checked, once or every month. We’ll agree the scope and the limits first.",
      options: [
        %{
          id: "review",
          name: "Review",
          line:
            "A one-off review of an application or agent integration. We validate each weakness, show how to reproduce it, rank the repairs and check that each fix holds.",
          items: [
            "Only weaknesses we reproduced, each with a priority.",
            "The inputs, steps and records that show each one.",
            "A proposed fix for each, most urgent first.",
            "Each fix checked again on the same inputs."
          ],
          link: {"Sample report", ~p"/services/security/sample-report"}
        },
        %{
          id: "monitoring",
          name: "Monitoring",
          line:
            "A monthly watch on the sites you own. We test them for weaknesses the way a careful attacker would, inside limits you agree, and nothing else.",
          items: [
            "You add the web addresses you want watched, each one a site you own.",
            "You prove each site is yours: a short DNS record, or a small file at a set address. No proof, no testing.",
            "We test the proven addresses, inside the limits you agreed.",
            "You get only the weaknesses we reproduced, each with a fix, and we retest after you fix."
          ],
          link: {"Your sites", ~p"/watchdog"}
        }
      ],
      rules: [
        "Only sites you’ve proven you own.",
        "Only the addresses you list, nothing beyond them.",
        "A rate you agree, and never anything that deletes or changes your data.",
        "Test accounts you make for us, never a real person’s login.",
        "We stop the moment you ask."
      ]
    }
  end

  @doc "A service, or Security, by its id."
  @spec fetch!(atom()) :: service() | security()
  def fetch!(:security), do: security()
  def fetch!(id), do: all() |> Map.new(&{&1.id, &1}) |> Map.fetch!(id)

  @doc "A service's page, by its id."
  @spec path(atom()) :: String.t()
  def path(:skills), do: ~p"/services/skills"
  def path(:evals), do: ~p"/services/evals"
  def path(:environments), do: ~p"/services/environments"
  def path(:models), do: ~p"/services/models"
  def path(:security), do: ~p"/services/security"
end
