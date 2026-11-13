defmodule TechtreeWeb.Services do
  @moduledoc """
  What Techtree sells: four services built around a customer's own workflows
  (Skills, Evals, Environments and Models), and Security beside them. Each is
  a paid custom project, delivered by people.

  Each service is one map: its name, a Lucide icon, a short line for the
  menus, its promise, its price level (1 to 4, shown as marks and never as a
  figure), what the customer brings, what we do, what they receive, the
  open-source tools we use on the project (each with its maker and its job
  there), notes, and the line that asks for a call. Models also carries a
  second opening line, its stages and the two comparisons it reports; a page
  shows those parts only where its service has them. Security has no price
  level. The terms (`terms/0`) are the same for all four. The header's
  Services menu (`TechtreeWeb.SiteMenu`), the home page's cards and credits,
  each service's page (`TechtreeWeb.ServiceLive`) and its Markdown all read
  them from here, so they never say different things. A new fact about a
  service is one more key.

  A tool is another company's open-source project, named with its maker
  (`label/1`) as one we use on a project, never as part of Techtree. A step of
  the work or a note is a list of words and links: a link is `{text, href}`.
  """

  use TechtreeWeb, :verified_routes

  @type words :: [String.t() | {String.t(), String.t()}]
  @type tool :: %{name: String.t(), maker: String.t(), href: String.t(), job: String.t()}
  @type stage :: %{name: String.t(), work: String.t(), result: String.t()}
  @type comparison :: %{name: String.t(), question: String.t(), answer: String.t()}
  @type service :: %{
          required(:id) => atom(),
          required(:name) => String.t(),
          required(:icon) => String.t(),
          required(:line) => String.t(),
          required(:promise) => String.t(),
          required(:price) => 1..4,
          required(:call) => String.t(),
          required(:bring) => [String.t()],
          required(:work) => [words()],
          required(:receive) => [String.t()],
          required(:tools) => [tool()],
          required(:notes) => [words()],
          optional(:more) => String.t(),
          optional(:stages) => [stage()],
          optional(:comparisons) => %{line: String.t(), items: [comparison()]}
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

  # Each library once; a service gives it its job there (`tool/2`).
  @skill_evaluator %{
    maker: "NVIDIA",
    name: "SkillEvaluator",
    href: "https://github.com/NVIDIA/SkillEvaluator"
  }
  @skill_opt %{
    maker: "Microsoft",
    name: "SkillOpt",
    href: "https://github.com/microsoft/SkillOpt"
  }
  @verifiers %{
    maker: "Prime Intellect",
    name: "Verifiers",
    href: "https://github.com/PrimeIntellect-ai/verifiers"
  }
  @prime_rl %{
    maker: "Prime Intellect",
    name: "prime-rl",
    href: "https://github.com/PrimeIntellect-ai/prime-rl"
  }
  @harbor %{
    maker: "Terminal-Bench",
    name: "Harbor",
    href: "https://github.com/harbor-framework/harbor"
  }
  @skill2env %{maker: "NVIDIA", name: "Skill2Env", href: "https://github.com/NVlabs/Skill2Env"}
  @repo2rlenv %{
    maker: "Hugging Face",
    name: "Repo2RLEnv",
    href: "https://github.com/huggingface/Repo2RLEnv"
  }
  @nemoclaw %{maker: "NVIDIA", name: "NemoClaw", href: "https://github.com/NVIDIA/NemoClaw"}

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
            named(@skill_evaluator),
            " to check the Skill’s quality and measure how the agent behaves with it."
          ],
          [
            "We use ",
            named(@skill_opt),
            " to propose changes to its instructions from scored attempts. The cases it learns from are kept apart from the final test."
          ],
          [
            "We use ",
            named(@verifiers),
            " to run the final comparison on cases the work never saw, keeping the model, tools and budgets fixed."
          ]
        ],
        receive: [
          "The revised Skill.",
          "Instructions to install it.",
          "A report on success, cost and regressions."
        ],
        tools: [
          tool(
            @skill_evaluator,
            "Checks the Skill’s quality and measures how the agent behaves with it."
          ),
          tool(@skill_opt, "Proposes changes to the Skill’s instructions from scored attempts."),
          tool(@verifiers, "Runs the final comparison and scores it.")
        ],
        notes: [
          [
            "SkillOpt improves the Skill’s written instructions. Repairing the scripts that come with a Skill is separate engineering, which we scope on the call."
          ]
        ]
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
          ["We use ", named(@verifiers), " to define the tasks and score them."],
          ["We use ", named(@prime_rl), " to run the full evaluation."],
          [
            "Where a task needs a working software environment, we package it with ",
            named(@harbor),
            "."
          ]
        ],
        receive: [
          "Reviewed test cases.",
          "Graders.",
          "Baseline results.",
          "An analysis of the failures.",
          "One command that reruns the suite."
        ],
        tools: [
          tool(@verifiers, "Defines the tasks and scores them."),
          tool(@prime_rl, "Runs the full evaluation."),
          tool(@harbor, "Packages the tasks that need a working software environment.")
        ],
        notes: [
          [
            "A better eval catches the failures that matter and scores the same work the same way every time. It need not produce a higher pass rate."
          ]
        ]
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
          ["We use ", named(@skill2env), " to generate Harbor tasks from a Skill."],
          [
            "We use ",
            named(@repo2rlenv),
            " to generate them from a repository, its past fixes and recorded agent sessions."
          ],
          ["We use ", named(@verifiers), " to run the tasks and score them."],
          [
            "An environment you already have, from Harbor, Prime or OpenEnv, starts with a compatibility review."
          ],
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
        tools: [
          tool(@skill2env, "Generates Harbor tasks from a Skill."),
          tool(
            @repo2rlenv,
            "Generates tasks from a repository, its past fixes and recorded agent sessions."
          ),
          tool(@verifiers, "Runs the tasks and scores them.")
        ],
        notes: [
          [
            "For ongoing work, failed attempts can propose new practice tasks, each one checked before it is admitted. The idea comes from ",
            {"the AutoEnvScaling research", "https://auto-env-scaling.github.io/"},
            "."
          ]
        ]
      },
      %{
        id: :models,
        name: "Models",
        icon: "brain-circuit",
        line: "A smaller model for repeated work",
        promise: "A smaller model for the work you repeat.",
        more:
          "Techtree tests your current AI workflow, builds a specialist, and measures the difference on cases it never saw. You keep the model, the evaluation and the evidence behind the decision.",
        price: 4,
        call:
          "Bring the one task you repeat and what it costs you today. We’ll agree the quality bar and the final test before any training.",
        bring: [
          "One repeated task, not a whole field: “classify a failed integration and pick the supported recovery step”, not “technical support”.",
          "Real inputs, and the outputs you accepted.",
          "What you run today, and what it costs."
        ],
        work: [
          [
            "We use ",
            named(@prime_rl),
            " for supervised fine-tuning, and for reinforcement learning when a project calls for it."
          ],
          [
            "We use ",
            named(@verifiers),
            " so that training and the final test share the same task definitions."
          ],
          [
            "When a project needs it, we use ",
            named(@nemoclaw),
            " to run supported agents inside OpenShell, under the rules you set."
          ]
        ],
        receive: [
          "A checkpoint or adapter.",
          "The training recipe.",
          "An evaluation package you can rerun.",
          "A deployment handover.",
          "A comparison with the original model, including the cost per successful task."
        ],
        stages: [
          %{
            name: "Qualify",
            work:
              "We define the task, the data permissions, the quality bar, the current cost and the limits on where the model can run.",
            result:
              "You get a scoped experiment and an approved budget, or a clear reason not to train."
          },
          %{
            name: "Baseline",
            work:
              "We test what you run today and an inexpensive existing model, then freeze the test and the cases it holds back.",
            result: "You learn whether training looks necessary at all."
          },
          %{
            name: "Candidate",
            work: "We curate examples and run one bounded training recipe.",
            result: "You get a versioned adapter or checkpoint, with its training record."
          },
          %{
            name: "Handover",
            work:
              "We test on unseen cases, measure the model as it would be served, and run it beside your current service in a trial you approve.",
            result:
              "You get the model files, the evaluation package, a cost report, its known limits, and how to switch to it or back."
          }
        ],
        comparisons: %{
          line: "Two questions, and we report them separately.",
          items: [
            %{
              name: "Training",
              question: "Did training improve the model?",
              answer:
                "The small base model against its trained version, on the same task and the same test."
            },
            %{
              name: "Replacement",
              question: "Should you replace what you run today?",
              answer:
                "Your current service against the proposed one, counting hosting, retries, response time and running cost."
            }
          ]
        },
        tools: [
          tool(@prime_rl, "Runs supervised fine-tuning and reinforcement learning."),
          tool(@verifiers, "Holds the same task definitions for training and for the test."),
          tool(
            @nemoclaw,
            "Optional, when a project needs it: runs supported agents inside OpenShell, under the rules you set."
          )
        ],
        notes: [
          [
            "Before training, we try a cheaper existing model and a better prompt or Skill. If that gets the saving, we say so."
          ],
          [
            "A candidate that falls short still gives you a paid, useful answer: whether the blocker is the data, an unclear task, model size, running cost or regressions."
          ],
          [
            "The figure we report is the total running cost per accepted outcome, at a quality level we agree. The one-time training cost is shown separately."
          ],
          [
            "We start with supervised fine-tuning on accepted examples, and add reinforcement learning when there is a reward we have validated."
          ],
          [
            "Results from our own runs are labelled a Techtree-run evaluation, not an independent audit."
          ]
        ]
      }
    ]
  end

  @doc "The terms every one of the four services is sold on. Never a figure."
  @spec terms() :: [String.t()]
  def terms do
    [
      "Model and compute usage is billed separately, under a cap we agree first.",
      "If you already have an eval or an environment, we reuse it. Missing foundations are quoted separately.",
      "You pay for the scoped work and its evidence. If the result shows no improvement, you still receive it, with the reason."
    ]
  end

  @doc "Every tool the four services use, once each, in the order they first appear."
  @spec tools() :: [tool()]
  def tools do
    all()
    |> Enum.flat_map(& &1.tools)
    |> Enum.uniq_by(& &1.href)
  end

  @doc "A project's name with its maker's: \"NVIDIA’s SkillEvaluator\"."
  @spec label(%{maker: String.t(), name: String.t()}) :: String.t()
  def label(%{maker: maker, name: name}), do: "#{maker}’s #{name}"

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

  defp tool(library, job), do: Map.put(library, :job, job)

  defp named(library), do: {label(library), library.href}
end
