# Regent guidance sources and copies

Paths below are relative to the Regent workspace. Use the selected revision's file
tree for exact locations; this map describes ownership and propagation. Saved file
inventories are dated evidence. Record unread/private paths and unavailable owners
explicitly; neither a file list nor this map proves that every string was reviewed.

## Shared sources

| Repository / location | Guidance it owns | Copies and consumers to trace |
|---|---|---|
| `repos/ash-template/skills/` | Regent-authored developer and workflow Skills, references, examples, helper descriptions | `.agents/skills/`, `.claude/skills/` aliases; selected public build Skills through `platform/lib/ash_template_web/agent_skills.ex`; plugins where packaged |
| `repos/ash-template/platform/priv/public/`, `priv/capabilities.json`, `priv/tool_manifest.json` | Generic product onboarding, discovery, docs, capabilities and tool descriptions | Public routes, generated OpenAPI, `platform/lib/ash_template_web/capabilities.ex`, browser registration, six site command descriptions |
| `repos/ash-template/platform/lib/ash_template_web/agent_start.ex`, `live/agent_start_live.ex`, `components/`, `live/` | Copyable start/pair instructions, labels, tips, account explanations, error/empty/loading states | Rendered `/start`, account pages, human-to-agent copy buttons, site adoptions |
| `repos/design-system/regent_ui/lib/regent/` and `regent_ui/assets/` | Shared account/profile/primitives copy, help, accessibility labels, tooltips and CSS-generated text | Each host's `regent_ui` pin; `mix regent_ui.assets`; copied `assets/vendor/regent_ui` and static assets |
| `repos/elixir-utils/ash_components/agents/lib/regent_agents/pairing_message.ex`, `refusal.ex` | Pairing prompts and shared error/recovery wording | Host controllers, tool/CLI failures, start-page copy, product Skills |
| `repos/elixir-utils/agent_access/` | Markdown/error behavior and signed browser-tool helper | `regent_agent_access.assets` copies, descriptions of proof/transport support |
| `repos/elixir-utils/credits/`, `points/`, `privy/`, `siwa/` | Accounting/rate labels, package READMEs, module docs, identity/signing contracts | Shared UI, host adapters, CLI mapping, product onboarding, release sequence |
| `repos/siwa-server/priv/static/skill.md`, `lib/siwa_server_web/help.ex`, static signer pages | Maintained signing guidance and signer UI/help | CLI sign-in flow and error hints; product docs reference it instead of duplicating protocol instructions |

## Five sites and the CLI

Every Phoenix site has guidance embedded in `platform/lib/*_web/{components,live,controllers}/`,
`platform/assets/js/`, optional templates and CSS, and model/action validation errors.
Inspect these even when the changed file is only a backend action. Do not treat every
`message` variable as user-facing without following its caller.

| Repository | Specific authored sources beyond the common layout |
|---|---|
| `repos/regents` | `platform/priv/public/`; `platform/lib/regents_web/agent_start.ex`; account/agent/Credits/Points components; `platform/priv/tool_manifest.json`; `cli/COMMANDS.md`, `cli/commands.json`; contract and staking notices |
| `repos/autolaunch` | `platform/lib/autolaunch_web/public_documents/{agents,docs}.md`; `public_page.ex`, `controllers/public_pages_controller.ex` and page HTML; auction/launch/trade wallet explanations; `platform/priv/tool_manifest.json`; `cli/COMMANDS.md`, `cli/commands.json`; legacy `cli/src/commands.js` and `cli/docs/` must be labelled by actual support |
| `repos/patchbay` | `skills/patchbay/SKILL.md`; `platform/lib/patchbay_web/forum/agent_pages.ex`; `controllers/agent_skills_controller.ex`; `platform/priv/public/`; `platform/priv/tool_manifest.json`; `platform/assets/js/webmcp/`; hosted MCP descriptions in application source; free/paid posting and refund recovery copy; site-directory/tool records authored at runtime |
| `repos/techtree` | `platform/priv/public/`; release/bootstrap source under `platform/lib/techtree/release/`, `platform/lib/techtree_web/release_info.ex`; `platform/priv/release/skills/` and examples; `platform/priv/tool_manifest.json`; `cli/` descriptors; local-versus-hosted execution, publication ownership and installation version claims |
| `repos/keyfleet` | `platform/priv/public/`; fleet/member/room/workspace components and wallet-button explanations; `platform/lib/keyfleet/capabilities.ex`; `platform/priv/tool_manifest.json`; `cli/` descriptors; launch gates, membership and wallet/agent authority wording |
| `repos/regents-cli` | `README.md`, `docs/`, `src/regents_cli/{app,auth,doctor,errors,next_steps,output,runner}.py`; `src/regents_cli/passkey.html`; `src/regents_cli/schemas/commands.v1.json`; `src/regents_cli/platforms/*/{commands.json,*.json,*.yaml}` bundled contracts; `src/regents_cli/techtree/cli.py`, `src/regents_cli/techtree/commands/`, packaged Skill/engine resources, installation and completion helpers |

The product owns its `cli/commands.json`/`COMMANDS.md` and HTTP contract. The unified CLI
packages versioned copies; updating the product does not update a published wheel.
Inspect the existing `check-cli`/contract-sync targets and CLI assembly/import machinery
before choosing a regeneration command. `make` targets may perform more than a read.

Public routes to follow from each router: `/llms.txt`, `/agents.md`, `/skill.md`, `/docs`,
`/start`, `/help`, `/commands.json`, `/openapi.json`, advertised capabilities, well-known
Skill aliases and per-page Markdown. Existence and source vary by site: do not assume a
route exists or label an unadvertised candidate's 404 a defect.

## Other first-party codebases

These are additional owners to consider when the change affects them. Inspect each
independently when available; otherwise record the missing repository or workspace
as an explicit coverage gap. This list does not assert that a scan occurred:

- `repos/ios`: Swift strings/accessibility/help and server tool schemas, prompts and errors.
- `repos/fly-sentinel`, `repos/sentinel-watch`: dashboard/admin copy, monitoring/recovery
  descriptions, notifications, operator runbooks and command/help text.
- `repos/media-web`: public/admin views, errors, API and deployment documentation.
- `repos/twigpine`: protocol/SDK/CLI usage, public docs and NatSpec/module docs.
- `repos/monorepo-template`: older template docs, contracts, SDK CLI, plugin-packaged
  Skills and developer instructions. Record whether an active consumer still uses them;
  do not silently promote this repository over ash-template.
- `repos/regents-cli-v2`: separate CLI source, assembly docs and packed command help.
  Establish active use before rewriting it or confusing it with the published CLI.
- `services/videocontrol`: UI/tool/CLI descriptions, product Skills, prompts, generated
  artifacts and workflow docs. Publication/scheduling capabilities are not authority to
  invoke them during a guidance review.
- `repos/video-creation/`: nested repository and loose guide sources; establish their
  separate identities and available revisions before inspecting them. They do not become product rollout dependencies merely by existing.
- Workspace `docs/`, `agent-docs/`, `AGENTS.md`, `CLAUDE.md`: active runbooks, cross-site
  contracts, decision records and dated handoffs. Review current references; preserve
  historical evidence. Exclude session stores and private runtime settings.

## Boundaries requiring explicit coverage notes

- Record the exact inspected refs and any separately reviewed working edits. Other
  worktrees can contain newer work: use the release owner's exact checkout/ref, or
  record it as unavailable. A saved inventory records only its dated inspected state.
- Trace generated first-party vendor copies. Record third-party dependency/submodule
  pins and whether their content was inspected; never infer coverage from a path
  listing. Check upstream usage docs only where the diff needs them.
- Database-authored tool directory descriptions, posts, uploaded Skills and external
  Pages are outside a filesystem inventory. Identify the owning table/publisher and
  public read path; do not export private content or claim it was reviewed.
- Screenshots, video, icons and other binary assets can contain words. Identify
  affected paths, then inspect them visually when tools permit. Otherwise record the
  missing visual evidence; a text search does not cover those words.
- Ignored build artifacts, old exports/backups and transcripts are not canonical copy.
  Live output must still be checked after the authorized release when claiming rollout
  completion.
