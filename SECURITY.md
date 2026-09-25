# Security policy

Please report suspected vulnerabilities privately through GitHub's private
vulnerability reporting for this repository. Do not open a public issue with
exploit details, credentials, private result data, or an unpatched weakness.

Include the affected component, the release or commit tested, reproduction
steps, impact, and any suggested mitigation. The maintainers will acknowledge
the report and coordinate validation and disclosure.

Security fixes target the current released artifacts and the active `main`
branch. Frozen historical releases may receive guidance instead of a new build
when a safe upgrade path is available.

## Where code runs

This section describes the environment work in Techtree: building tasks from
a repository or from a Skill, and running an agent on those tasks. All of it
happens on your own machine, in your own Docker.

**Building tasks from a repository** (`techtree forge build`). Techtree clones
the repository and builds one starting image from it. That build is the one
step that may use the internet: it installs the repository's own dependencies,
the way the repository's setup asks. The repository's code and tests then run
only inside containers made from that image, with no network.

**Building tasks from a Skill.** Each task's image is built with the network
switched off, from the task's own folder and nothing else. The only outside
images it may start from are the ones this release lists by exact digest,
which Techtree downloads by that digest before the build starts. A task
recipe that tries to download anything fails, and its build log is kept.

**Checking and running tasks.** Every check of a task, and every attempt by
an agent, runs in a new container that has no network and fixed limits of 2
CPUs and 4 GB of memory. These containers are thrown away when they finish;
when a step times out or is interrupted, Techtree tries to remove them and
reports what happened. The agent's own commands run inside such a container. The agent itself, your Hermes, runs
on your machine and sends its requests to the model provider you signed in
to, after you approve the run.

**What Techtree treats as content, not instructions.**

- Techtree never runs a Skill's files. It lists and fingerprints them, and
  anything it cannot read as plain text is left out or refuses the Skill.
  What a Skill says it may use (for example `allowed-tools`) grants nothing.
- A Skill's text reaches a model only when you approve the planning or
  building step that says so, and that model has no tools other than text.
  Tasks it writes, including their reference answers, run only inside the
  offline containers above.
- Text inside a Skill, a repository, or a run's output cannot approve a step,
  change a limit, or send anything off your machine. Approval comes only from
  the command a person runs after reading the review Techtree prints.
