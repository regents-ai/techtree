defmodule TechtreeWeb.Services do
  @moduledoc """
  What Techtree sells: four services built around a customer's own workflows
  (Skills, Evals, Environments and Models), and Security and Swarm Verify
  beside them (`others/0`). Each is a paid custom project from Regents Labs.

  Each service is one map: its name, a Lucide icon, a short line for the
  menus, its promise, its price level (1 to 4, shown as marks and never as a
  figure), the steps of the work in order, what the customer receives, the
  open-source tools for the project (each with its maker, its job there and
  its status), notes, and the line that asks for a call. Every library is also
  listed once (`libraries/0`) with what it does in a Techtree job, for the home
  page's credits. Models also carries
  a second opening line and the two comparisons it reports; a page shows those
  parts only where its service has them. Security and Swarm Verify have no
  price level, and each is a map of its own shape. The
  terms (`terms/0`) are the same for all four. The header's Services menu
  (`TechtreeWeb.SiteMenu`), the home page's cards and credits, each service's
  page (`TechtreeWeb.ServiceLive`) and its Markdown all read them from here, so
  they never say different things. A new fact about a service is one more key.

  The steps are the whole plan, as the service is designed to run. A step
  that runs something carries a status (`status_line/0`): Delivered on a
  customer's project, Tested in Techtree's own runs, or Planned. A step that is
  people agreeing, reviewing or handing over carries none. A tool is another
  company's open-source project, named with its maker (`label/1`), never as
  part of Techtree, and has a status of its own; a page groups a service's
  tools by status (`by_status/1`) and leaves out a status none of them has. A
  step or a note is a list of words and links: a link is `{text, href}`.
  """

  use TechtreeWeb, :verified_routes

  @type words :: [String.t() | {String.t(), String.t()}]
  @type status :: :delivered | :tested | :planned
  @type step :: %{name: String.t(), status: status() | nil, words: words()}
  @type library :: %{
          name: String.t(),
          maker: String.t(),
          href: String.t(),
          status: status(),
          line: String.t()
        }
  @type tool :: %{
          name: String.t(),
          maker: String.t(),
          href: String.t(),
          status: status(),
          line: String.t(),
          job: String.t()
        }
  @type comparison :: %{name: String.t(), question: String.t(), answer: String.t()}
  @type service :: %{
          required(:id) => atom(),
          required(:name) => String.t(),
          required(:icon) => String.t(),
          required(:line) => String.t(),
          required(:promise) => String.t(),
          required(:price) => 1..4,
          required(:call) => String.t(),
          required(:steps) => [step()],
          required(:receive) => [String.t()],
          required(:tools) => [tool()],
          required(:notes) => [words()],
          optional(:more) => String.t(),
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
  @type stage :: %{name: String.t(), line: String.t()}
  @type swarm_verify :: %{
          id: :swarm_verify,
          name: String.t(),
          icon: String.t(),
          line: String.t(),
          promise: String.t(),
          more: String.t(),
          call: String.t(),
          workflow: %{line: String.t(), stages: [stage()]},
          failures: [String.t()],
          steps: [step()],
          receive: [String.t()],
          loop: String.t(),
          limits: [String.t()],
          tools: [tool()]
        }

  @statuses [:delivered, :tested, :planned]

  # Each library once, with its status and what it does in a Techtree job
  # (`line`, for the home page's credits); a service gives it its job there
  # (`tool/2`).
  @verifiers %{
    maker: "Prime Intellect",
    name: "Verifiers",
    href: "https://github.com/PrimeIntellect-ai/verifiers",
    status: :tested,
    line: "Holds the cases and scores every attempt, from the first measure to the final test."
  }
  @environments_hub %{
    maker: "Prime Intellect",
    name: "Environments Hub",
    href: "https://app.primeintellect.ai/dashboard/environments",
    status: :tested,
    line: "Supplies the environment a Climb runs, pinned by version."
  }
  @prime_rl %{
    maker: "Prime Intellect",
    name: "prime-rl",
    href: "https://github.com/PrimeIntellect-ai/prime-rl",
    status: :planned,
    line:
      "Trains a smaller model on your accepted examples, then with reinforcement learning, using task scores as feedback."
  }
  @skill_evaluator %{
    maker: "NVIDIA",
    name: "SkillEvaluator",
    href: "https://github.com/NVIDIA/SkillEvaluator",
    status: :tested,
    line: "Reviews a Skill as it is written."
  }
  @nemotron %{
    maker: "NVIDIA",
    name: "Nemotron",
    href: "https://www.nvidia.com/en-us/ai-data-science/foundation-models/nemotron/",
    status: :tested,
    line: "The small open model in each published demonstration, run on our own machine."
  }
  @skill2env %{
    maker: "NVIDIA",
    name: "Skill2Env",
    href: "https://github.com/NVlabs/Skill2Env",
    status: :planned,
    line: "Generates practice tasks from a Skill."
  }
  @nemoclaw %{
    maker: "NVIDIA",
    name: "NemoClaw",
    href: "https://github.com/NVIDIA/NemoClaw",
    status: :planned,
    line: "Runs agents inside OpenShell, under the rules you set."
  }
  @repo2rlenv %{
    maker: "Hugging Face",
    name: "Repo2RLEnv",
    href: "https://github.com/huggingface/Repo2RLEnv",
    status: :planned,
    line:
      "Generates practice tasks from a repository, its past fixes and recorded agent sessions."
  }
  @harbor %{
    maker: "Terminal-Bench",
    name: "Harbor",
    href: "https://github.com/harbor-framework/harbor",
    status: :tested,
    line:
      "Checks each practice task in a sealed setup: the worked solution passes and doing nothing scores zero."
  }
  @skill_opt %{
    maker: "Microsoft",
    name: "SkillOpt",
    href: "https://github.com/microsoft/SkillOpt",
    status: :tested,
    line: "Proposes revisions to a Skill from scored attempts, measured against a plain rewrite."
  }
  @hermes %{
    maker: "Nous Research",
    name: "Hermes",
    href: "https://github.com/NousResearch/hermes-agent",
    status: :tested,
    line: "Hosts Techtree’s plugin, and is the agent each Climb evaluates."
  }
  @everystate %{
    maker: "Matt Carey",
    name: "Everystate",
    href: "https://github.com/mattzcarey/everystate",
    status: :planned,
    line:
      "Checks every reachable state of a fleet’s coordination model, and recorded runs against it."
  }

  # Every library, grouped by maker in the order the home page credits them.
  @libraries [
    @verifiers,
    @environments_hub,
    @prime_rl,
    @skill_evaluator,
    @nemotron,
    @skill2env,
    @nemoclaw,
    @repo2rlenv,
    @harbor,
    @skill_opt,
    @hermes,
    @everystate
  ]

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
        steps: [
          step(
            "Intake",
            nil,
            [
              "You bring your Skill, the agent and model that use it, real examples of the work, and the failures you already know about."
            ]
          ),
          step(
            "Success",
            nil,
            [
              "We agree what better means for you, such as more correct work, fewer serious mistakes or a lower cost, and set a budget cap before anything runs."
            ]
          ),
          step("Quality check", :tested, [
            named(@skill_evaluator),
            " reviews the Skill as it is written."
          ]),
          step("Baseline", :tested, [
            "We measure your current Skill with your agent through ",
            named(@verifiers),
            ". We repeat the baseline evaluation to measure how much results vary. The cases for the final test are set aside, and the improvement never sees them."
          ]),
          step("Improvement", :tested, [
            named(@skill_opt),
            " proposes revisions from scored attempts on the working cases, and a single plain rewrite is made beside it."
          ]),
          step("Selection", :tested, [
            "The original and both revisions are measured on a separate set of cases, and the one that solves the most is chosen, so you see what the automatic revision adds over a plain rewrite."
          ]),
          step("Final test", :tested, [
            "A single run on the untouched cases, scored by ",
            named(@verifiers),
            ", with the model, tools and limits held fixed. When the test does not establish a difference between the two versions, we report the result as inconclusive."
          ]),
          step(
            "Handover",
            nil,
            [
              "You get the revised Skill, its report, and one command that reruns it. If the Skill did not improve, you still get the result and the reason."
            ]
          )
        ],
        receive: [
          "The original Skill and the revised one.",
          "A report covering cost, new errors, and uncertainty in the results.",
          "The exact setup it ran on.",
          "One command that reruns it."
        ],
        tools: [
          tool(@skill_evaluator, "Reviews the Skill as it is written."),
          tool(@skill_opt, "Proposes revisions to the Skill from scored attempts."),
          tool(@verifiers, "Runs the final test and scores it.")
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
        steps: [
          step(
            "Intake",
            nil,
            [
              "You bring the job, with examples of good work and bad, or an eval you already have."
            ]
          ),
          step("Success", nil, ["We agree what the test must tell you."]),
          step("Review", nil, [
            "You approve the test cases before we use them to score your agent."
          ]),
          step("Build", :tested, [
            "We package the cases and their scoring as an environment for ",
            named(@verifiers),
            "."
          ]),
          step("Scoring check", :planned, [
            "We show that the scoring accepts known-good work and rejects plausible mistakes."
          ]),
          step("Baseline", :tested, [
            "We measure your current agent or model with ",
            named(@verifiers),
            ", several times over, and explain where it fails."
          ]),
          step("Full run", :planned, [
            "For a large test, ",
            named(@prime_rl),
            " runs the whole evaluation at scale."
          ]),
          step("Handover", nil, [
            "You get the test suite, baseline scores, and a report of where your agent fails."
          ])
        ],
        receive: [
          "Reviewed test cases.",
          "Scoring for every case.",
          "Scores for what you run today.",
          "An analysis of the failures.",
          "One command that reruns the whole test."
        ],
        tools: [
          tool(@verifiers, "Packages the cases, runs them and scores them."),
          tool(@prime_rl, "Runs the whole evaluation at scale.")
        ],
        notes: [
          [
            "A better eval catches the failures that matter and scores the same work the same way every time. It need not produce a higher pass rate: it gives you a test you can trust."
          ]
        ]
      },
      %{
        id: :environments,
        name: "Environments",
        icon: "boxes",
        line: "Train and test agents on your tasks",
        promise: "We build environments for training and testing agents on your tasks.",
        price: 3,
        call:
          "Bring the workflow, the Skill or the repository. We’ll agree which tasks the environment should hold.",
        steps: [
          step(
            "Intake",
            nil,
            [
              "You bring the workflow, a Skill or a repository. An environment you already have, on Prime Intellect’s Environments Hub, in Harbor’s format or in OpenEnv, starts with a review of what can be reused."
            ]
          ),
          step("Success", nil, ["We agree what an agent should be able to do."]),
          step("Tasks", :planned, [
            "Tasks come from you, or we generate them: from a Skill with ",
            named(@skill2env),
            ", or from a repository, its past fixes and recorded agent sessions with ",
            named(@repo2rlenv),
            "."
          ]),
          step("Soundness", :tested, [
            "We check that reference solutions pass, known incorrect solutions fail, and empty attempts score zero. Each task runs with ",
            named(@harbor),
            " in a sealed setup with no network."
          ]),
          step("Baseline", :planned, [
            "We measure an agent on the tasks with ",
            named(@verifiers),
            "."
          ]),
          step("Handover", nil, [
            "You get the environment, its tasks with worked solutions and scoring, and commands to test and train agents on it."
          ])
        ],
        receive: [
          "An environment that resets between runs.",
          "Realistic tasks, with their tools and sample data.",
          "A worked solution for each task.",
          "Scoring.",
          "Ready-made commands to test agents on it and to train them."
        ],
        tools: [
          tool(@skill2env, "Generates practice tasks from a Skill."),
          tool(
            @repo2rlenv,
            "Generates tasks from a repository, its past fixes and recorded agent sessions."
          ),
          tool(@harbor, "Checks each task in a sealed setup with no network."),
          tool(@verifiers, "Runs the tasks and scores them.")
        ],
        notes: [
          [
            "For ongoing work, we can turn failed runs into new tasks, with each task reviewed before it is added. The idea comes from ",
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
        steps: [
          step(
            "Intake",
            nil,
            [
              "You bring the work you repeat, with real examples: one task, such as “classify a failed integration and pick the supported recovery step”, not a whole field."
            ]
          ),
          step("Qualify", :tested, [
            "We check whether a smaller model is right for this, and try a cheaper existing model first."
          ]),
          step(
            "Success",
            nil,
            [
              "We agree the target, and split your examples once: some for training, and a set the model never sees."
            ]
          ),
          step("Baseline", :tested, [
            "We measure the small model and your current model with ",
            named(@verifiers),
            " before any training."
          ]),
          step("Plan", :tested, [
            "We write a training plan in the format of ",
            named(@prime_rl),
            ", with its cost. Training starts after you approve the plan and budget."
          ]),
          step("Training", :planned, [
            named(@prime_rl),
            " trains the model on your accepted examples first. When the project calls for it, training continues with reinforcement learning, using task scores as feedback."
          ]),
          step("Final test", :planned, [
            "We test the trained model against the original on the unseen set with ",
            named(@verifiers),
            ", including the cost per successful task."
          ]),
          step("Handover", :planned, [
            "You get the trained model, its training recipe, and a test package you can rerun, with help putting the model into service. When agents need to run under rules you set, we run them inside OpenShell with ",
            named(@nemoclaw),
            "."
          ])
        ],
        receive: [
          "The trained model files.",
          "The training recipe.",
          "A test package you can rerun.",
          "Help putting the model into service.",
          "A comparison with the original model, including the cost per successful task."
        ],
        comparisons: %{
          line: "Two questions, and we report them separately.",
          items: [
            %{
              name: "Training",
              question: "Did training improve the model?",
              answer:
                "The small model before and after training, on the same task and the same test."
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
          tool(@verifiers, "Holds the tasks that training and the final test share."),
          tool(
            @prime_rl,
            "Trains the model on your accepted examples, then with reinforcement learning, using task scores as feedback."
          ),
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
            "If the model misses the target, we explain where it fell short: the data, an unclear task, model size, running cost or new mistakes."
          ],
          [
            "The figure we report is the total running cost per accepted outcome, at a quality level we agree. The one-time training cost is shown separately."
          ],
          [
            "Training starts on your accepted examples. Reinforcement learning comes next, once we have checked the scoring."
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
      "If you already have an eval or an environment, we reuse it. We quote separately for any evaluation or training environment we need to build.",
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

  @doc """
  Every open-source project Techtree builds on, once each, grouped by maker
  (Prime Intellect, NVIDIA, Hugging Face, Terminal-Bench, Microsoft, Nous
  Research, Matt Carey): the services' tools and the ones Techtree's own runs
  use, each with what it does in a Techtree job and its status.
  """
  @spec libraries() :: [library()]
  def libraries, do: @libraries

  @doc "A project's name with its maker's: \"NVIDIA’s SkillEvaluator\"."
  @spec label(%{maker: String.t(), name: String.t()}) :: String.t()
  def label(%{maker: maker, name: name}), do: "#{maker}’s #{name}"

  @doc "A status as the one word a page shows."
  @spec status_name(status()) :: String.t()
  def status_name(:delivered), do: "Delivered"
  def status_name(:tested), do: "Tested"
  def status_name(:planned), do: "Planned"

  @doc "The line under a service's steps that says what its status words mean."
  @spec status_line() :: String.t()
  def status_line,
    do: "Tested: we have run it ourselves. Planned: part of the design, not yet run."

  @doc """
  Tools grouped by status, Delivered first, then Tested, then Planned, each
  group in the order given. A status none of them has is left out.
  """
  @spec by_status([tool()]) :: [{status(), [tool()]}]
  def by_status(tools) do
    groups = Enum.group_by(tools, & &1.status)
    for status <- @statuses, groups[status], do: {status, groups[status]}
  end

  @doc "Security, offered beside the four: a one-off review or monthly security testing."
  @spec security() :: security()
  def security do
    %{
      id: :security,
      name: "Security",
      icon: "shield-check",
      line: "Review or test what you run",
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
            "Monthly security testing for your websites. We test for exploitable vulnerabilities within the scope you approve.",
          items: [
            "You add the web addresses you want tested, each one a site you own.",
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

  @doc """
  Swarm Verify, offered beside the four: checks of the coordination behind a
  large agent fleet, by three methods, none of them run yet.
  """
  @spec swarm_verify() :: swarm_verify()
  def swarm_verify do
    %{
      id: :swarm_verify,
      name: "Swarm Verify",
      icon: "network",
      line: "Verify how agents coordinate",
      promise:
        "Find duplicate work, conflicting ownership, budget overruns and incomplete shutdowns in a large agent fleet before they reach production.",
      more:
        "For engineering teams and agent platform companies whose 100 to 500 agents share tasks, resources or spending limits.",
      call:
        "Tell us how your agents share their work. Swarm Verify is open to design partners with shared-state agent workloads.",
      workflow: %{
        line: "The first workflow Swarm Verify covers, in five stages.",
        stages: [
          %{name: "Claim", line: "An agent takes a task and holds it under a lease."},
          %{name: "Reserve", line: "It sets aside its share of a spending limit."},
          %{
            name: "Execute",
            line: "It does the work, including actions outside your systems, such as an email."
          },
          %{name: "Commit", line: "It records the result."},
          %{
            name: "Release",
            line: "It gives back the task, the budget and anything else it held."
          }
        ]
      },
      failures: [
        "An agent’s lease expires, a second agent takes the task over, and the first returns late and overwrites the new result.",
        "A retry repeats a step that already finished.",
        "An action outside your systems, such as an email, happens twice.",
        "A canceled task keeps running, or stops without giving back what it held."
      ],
      steps: [
        step("Model checking", :planned, [
          "We write the rules your agents follow as a model with stated bounds, such as how many agents, tasks and retries, and check every state it can reach within them with ",
          named(@everystate),
          "."
        ]),
        step("Swarm experiments", :planned, [
          "We run the fleet with faults injected on purpose: crashes, delays, retries, leases that expire and cancellation messages that never arrive."
        ]),
        step("Execution conformance", :planned, [
          "We check runs your fleet has recorded against the same stated rules, step by step, with ",
          named(@everystate),
          "."
        ])
      ],
      receive: [
        "The first transition that breaks a rule, with every step that led to it.",
        "The agents it affects.",
        "A replay a coding agent can use to propose a fix.",
        "Regression checks that rerun before each release."
      ],
      loop:
        "Then one loop: change the harness, run the checks, reproduce a failure, repair it and run the checks again.",
      limits: [
        "Every report states its bounds, its assumptions and any telemetry it was missing.",
        "A small model that passes is not proof that the whole fleet is correct.",
        "Enforcement belongs in your own queue, budget or tool service, never in Swarm Verify."
      ],
      tools: [
        tool(
          @everystate,
          "Explores every state the model can reach, and compares recorded runs with it. A TLA+ model checker written in Rust, under the MIT license."
        )
      ]
    }
  end

  @doc "Security and Swarm Verify, offered beside the four, in the order every list shows them."
  @spec others() :: [security() | swarm_verify()]
  def others, do: [security(), swarm_verify()]

  @doc "A service, Security or Swarm Verify, by its id."
  @spec fetch!(atom()) :: service() | security() | swarm_verify()
  def fetch!(id), do: (all() ++ others()) |> Map.new(&{&1.id, &1}) |> Map.fetch!(id)

  @doc "A service's page, by its id."
  @spec path(atom()) :: String.t()
  def path(:skills), do: ~p"/services/skills"
  def path(:evals), do: ~p"/services/evals"
  def path(:environments), do: ~p"/services/environments"
  def path(:models), do: ~p"/services/models"
  def path(:security), do: ~p"/services/security"
  def path(:swarm_verify), do: ~p"/services/swarm-verify"

  defp step(name, status, words), do: %{name: name, status: status, words: words}

  defp tool(library, job), do: Map.put(library, :job, job)

  defp named(library), do: {label(library), library.href}
end
