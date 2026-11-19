# Techtree feature map

Everything a person or an agent can do on Techtree.

`make live-check` is the one check that reads the live site, after a release
(`scripts/live-check.sh`). In plain requests, signed out, it reads the commit the
site runs, that every public page answers with an HTML page, and that every
public document answers; nothing is rendered, so no page's scripts, layout,
browser tools or theme switch are looked at. Then, signed with this Mac's own
agent key through the regents command line, it reads who the agent is and that
it is paired (`agents whoami`), and its person's Points (`account points`). It
writes nothing; the signed reads change only the time the site last saw the
agent.

## Public pages (signed out)

- Read the home page in order: the promise with Book Call, the four services (Skills, Evals, Environments, Models), each card naming its tools under their status (Tested or Planned, never an empty status), Factory (the four things a first run on Prime Intellect's Model Factory needs, in order, each linked to the service that delivers it, then the Factory guide and Model Factory's own page), the demonstrations, labelled for what they are, the six steps, Built on (every library from `Services.libraries/0`, in its order, under its maker's logo or name, each linked with its status and its job) and a closing Book Call, with nothing scrolling sideways
- Open a service from its card on the home page, each card showing its price level as one to four filled marks of four, read aloud as "Price level N of 4", with no figure for money; the marks move nothing as the page loads
- See every comparison side by side as a demonstration: the original and improved Skill's share of attempts solved, counting up to what the server wrote without moving the page, the verdict the figures earn (an inconclusive one shown as plainly as an improvement), its page and the Skill's GitHub and skills.sh links
- See every moving picture on the home page drawn over its still; with less motion asked for, or with no WebGPU, each keeps its still
- See what Techtree is built on, each project under whose it is with a link to its own page (Prime Intellect's Verifiers, prime-rl, Environments Hub and Model Factory; NVIDIA's SkillEvaluator, Skill2Env and Nemotron; Nous Research's Hermes; Matt Carey's Everystate): on the home page under each maker's own logo, on the same light plate in both themes, the only logos on the site
- Open each service page (Skills, Evals, Environments, Models and Security): its numbered steps, each one that runs something marked Tested or Planned with one line saying what the two words mean, what you receive, the open-source tools grouped by status (each named with its maker, linked, with its job and links to the published results it did a part in; a status no tool has never shows), the shared terms and the service's notes, then its price level with "Quoted on a call." beside Book Call or email; Models adds its two comparisons
- Open Swarm Verify, beside Security: who it is for, the five stages of the first workflow it covers, the failures it looks for, its three methods (model checking, swarm experiments and execution conformance), each marked Tested, the public demonstration they ran on (lease, budget and cancellation models checked with Matt Carey's Everystate and TLC, and a simulated run of 128 workers, linked at one fixed revision of `swarm-verify/`), what you receive and the loop after it, its limits (one says no customer fleet has been checked yet), the library it is built on (Matt Carey's Everystate, Tested), then Contact with the email named Swarm Verify and the enquiry form with Swarm Verify chosen; no price level and no figure for money
- Open each inner page (Results, one Result, Wallet Bench, Formal, the six services, Docs, Agents, Changelog, Blog, About and Account) on its dark band: its name as the one page title, its promise, its main action and, outside Account, Book Call; on a wide screen a dot picture of its own beside it
- Follow a retired address (/start, /verify, /docs/method, /repo2rlenv, /train, the Verify, Cyber Assist and Watchdog offers and their sample reports) to the page that took its place, moved for good
- Read Run locally, and copy the install steps when a release is published
- Read the docs
- Read Factory in the Docs (`/docs/factory`): what a company needs before its first run on Prime Intellect's Model Factory, from deciding to improving, and which service covers each step; listed on `/docs`, in the guides menu and in the sitemap
- Turn the light and dark theme with the switch in the header, by press, Space or Enter, once a press, from a device set to light or to dark; the choice holds over a reload; the header keeps one row at 320 wide
- Open the header's Services menu by press or by key: Tab walks into it, Escape closes it and gives focus back, a press outside closes it; it lists the four services with Security and Swarm Verify under Also, and Results and Docs sit beside it; below a wide screen the same pages open in one Menu sheet; the footer lists every page the header does
- See Book Call in the header, the Menu sheet, the home page and each service page only when a booking page is set; it opens that page in a new tab
- Browse and filter published Results
- Open one Result
- Share a Result's link and see its own picture, while every other page shows the site's
- A search engine reads Techtree as a business within Regents Labs, with one service for each service page and no price
- See Wallet Bench tests, or why there are none
- Read the Wallet Bench score grid for each test, and the list; on the Wallet grid a pair whose newest install did not pass reads "No install" and opens that install result
- Open a score's result window, download its full results, close it back to the score
- Read the Wallet Bench scores as data from another site (`/wallet-bench.json`), a wallet test the install kept from starting included
- Open one Wallet Bench test and its evidence: each test leads with its outcome and why, every check is marked Yes, No or Open, a safety failure outside the checks says so, each score at the top jumps to its test, and a test that stopped says why in plain words
- See on Results every comparison Techtree ran itself, newest first, or none when there are none, with Wallet Bench and Formal linked below
- Open one comparison: the Skill with its GitHub and skills.sh links, the task, the original and improved Skill's attempts solved on the final test as two bars, the method with the choosing step's figures, every case with its change, the tools, the report to download, and how to check it
- See the final test's totals, each case's change and the verdict worked out from the data themselves (a chance reading at or above the agreed level is inconclusive, whichever side solved more), never taken from the file
- Read Proof in the Docs: what a Result proves and how to check one on your own computer
- Read a Climb
- Read the changelog, blog, About, which opens on "Open-source tools. Paid custom projects.", Privacy, Terms, the tdd example, the Security sample report, and Techtree Formal
- Land on a page that doesn't exist and find the way home
- Keep reading Home, Run locally, Docs, Results and Wallet Bench while the database is down: a wallet test's page says the tests can't be shown (never that the test is missing) and a refresh keeps what it shows; its record, downloads and the bench's Markdown answer 503 asking to try again
- On the Security service, press Agent Message beside the email button: its window gives three texts to paste into an agent (CLI, MCP, WebMCP) that name the tool, the command and the address the site publishes; each fits the screen and copies exactly as shown, at 1280 and 390 wide; Escape, the X or a press beside it closes it; a visitor sees no form; the service's Markdown gives the same three texts; no other service has the button

## Signed in

- Open the account menu from their name on every page: their agents with Manage, Pair New Agent, Manage Account and Sign out; it hangs under the button inside the screen at 1280, 390 and 320 wide, the page still fits, a press outside or Escape closes it with focus back on the button, and with less motion it appears at once
- Turn the light and dark theme with the switch in the account menu, at 1280 and 320 wide, by press, Space or Enter; opening the menu moves nothing on the page, turning the switch never changes the menu's size, the choice holds over a reload and a live page change, and there is no second switch in the header
- Pair New Agent in the account menu, and in the Agents list, opens the pairing window over the page they are on, every press, with the keyboard on the agent dropdown and the list of agents open; the menu closes first; Close, the backdrop or Escape close it, Escape closing an open list first; closed, focus goes back to what opened it; Manage Account opens the Account page and closes the menu; every signed-in page holds the one window
- Choose an agent in the pairing window and copy its message; the window keeps one height whatever is chosen; the agent's picture sits in a low band and choosing moves nothing under it; the list drops in and leaves with a short move, a press during it counts, and with less motion it opens and closes at once; each agent keeps its own code until a new one is asked for; a form sent back with nothing chosen leaves the box as it is
- See their agents and Pair New Agent on the Agents tab (/account/agents), and their profile on the Account tab, at 1280, 390 and 320 wide, with nothing scrolling sideways
- Save their Public Display Name on the Account tab at 1280 and 390 wide: the name stays in the box, the name in the header changes without a reload, and Save doesn't move; a name with a hidden character is refused beside Save and nothing changes
- Have their profile made when they sign in, then read it and change their name with this site's own sign-in; a change without the session's forms token is refused and changes nothing, signed out nothing is answered, and no one reads or changes another person's
- See Results signed in at 1280 and 390 wide, the newest comparison first, opening it with every case in its table
- On a phone, see the open Menu over the page, with the page and footer out of reach until it closes; on a short phone screen the account menu ends inside the screen and reaches Sign out
- See public pages signed out, and stay signed in, while the database is down
- On Watchdog, add a site you own, get its DNS record or file to publish, press Check to prove ownership, and add, turn off or remove the addresses on it; only your own list is seen or changed, and an address can't be active until its site is proven
- On the Security service, open Agent Message and leave the team a message from its form: an empty message is refused under its field when the field is left, a sent one shows its receipt and clears the form, and the window stays open, at 1280 and 390 wide
- From the Contact section of the home page or any service page, signed in or not, send the team an inquiry: name, work email, company, a service (a service's own page has it chosen) and what you want to improve. Each field left wrong is refused under itself and Send puts the keyboard on the first; a sent one gives way to a note, which takes the keyboard; a filled-in field people never see keeps nothing; past 5 an hour from one network address the form says so and keeps nothing
- As one of the site's admins (`REGENT_CREDITS_ADMINS`), read every message left for the team at /admin/messages, and every inquiry under its Inquiries tab, newest first, 50 a page; anyone else, signed in or not, gets the not-found page
- On the Projects tab (/account/projects), see the projects Techtree's team delivered to you, newest first, or a note that there are none; open one: its verdict, the original and the selected Skill's final test as two bars against the pass bar with their figures, every case with the worse ones marked, the candidates, the setup and the report; Download saves the exact package, whose SHA-256 is the Checksum shown, at 1280 and 390 wide, readable in light and dark. Another person, signed in, finds none of it, not even its download; signed out, a project asks you to sign in
- Read a delivered Evals, Environments or Models package with its service verdict and report, and download the same archive. Its agent read uses the same keys, with the Skills comparison fields null. The upload limit stays 5 MiB.
- As one of the site's admins, on the Projects tab of /admin/messages, upload a package (one .tar.gz, up to 5 MB): it is checked at once, a package that isn't exactly what the factory makes is refused under its field with nothing kept, and a good one is previewed; find its customer by a wallet their account signed in with, in any case, or their Privy id, a search that finds no one staying to be corrected; Deliver puts it first in their Projects and records who delivered it and when; Withdraw asks first, takes it from the customer, deletes its package and report, and keeps who withdrew it and when. One package goes to one customer once while that delivery stands. Anyone else gets the not-found page, and only admins deliver, find or withdraw
- Sign in with Privy
- Rename a paired agent from its window on the Agents page, at both widths; a name with hidden characters is refused under the Name field itself; Unpair there asks in the site's own confirm window, opened over the agent's (Cancel keeps the agent, Unpair takes it off the list)
- See the three most recently active agents in the account menu
- Every agent kind the library knows, Claude Duet included, draws its picture in the agents list and the account menu, so an agent paired on another site never breaks a person's list here
- Pair an agent end to end
- Wallets and Connections tabs with real data

## Agents and machines

- Read `/agents.md`, `/llms.txt`, `/openapi.json` and the bootstrap
- Read whether the site is serving at `/healthz` and `GET /api/v1/health`, which also says whether the running release's migrations are all applied (`migrations_applied`) and stays 200 while one waits
- Read the public pages, `/sitemap.xml`, `/llms.txt`, `/agents.md` and a Wallet Bench test's `results.json` up to 120 times a minute from one address; the next read that minute is refused with 429 and how many seconds to wait, another address reads on, and the health check is never counted
- Read the catalog, Climbs, objects and publications
- Publish a Result and report a Climb
- Sign in with its wallet and use the four agent addresses (publications, Model Climb reports, `/api/v1/account`, `/api/v1/profile`) only while acting as its person: unsigned 401, unpaired `agent_not_paired`, person not here `person_not_here`, and an unpairing during the request sends none of the person's data
- A new account, each linked social account and a paired agent offer their one-time Points award once, inside the save that earns it; a sign-in that changes nothing offers nothing, and an agent's award names its wallet
- An account, its linked social account and its paired agent from before the Points start earn their one-time Points at the start, once, through this site's own checks; those from after the start that Points has not recorded, such as before the site switched Points on, earn once at the time they happened; and a later run offers nothing more for an account that has earned. The hourly line runs it, and once a run succeeds no other runs that day
- A linked social account earns only while it is linked to the same account when the award is written: one removed before then earns nothing, and one moved to another account earns nothing for the first and once for the account that holds it, when its own offer is checked or, if that offer was turned away while the first award waited, at the next start run
- Read the Train comparisons as data (`/train.json`, or the browser tool `train_comparisons`), each page as Markdown at its own address, and download a comparison's report with its digest as entity tag
- Read its person's Points: their figures, the actions still open, and the leaderboard with their own row marked and a person with no name shown by their wallet; nothing at all while the shared board is not read
- Read its person's shared profile and set their public name, and no one else's
- List, read and download the projects Techtree's team delivered to its person (`GET /api/v1/account/projects`, `/{id}` and `/{id}/package`, or the browser tools `account_projects` and `account_project`), and find no one else's
- The board every signed-in reader shares: a refused reading keeps the one held, every reading offered reports its size against the limit, a failed first read is marked, an unchanged reading wakes no page, the kind holds one key, and measuring survives the table being away
- A signed POST under `/api` keeps its exact bytes, so the sign-in service checks the digest of what the agent signed
- Use a page's signed browser tools through its own browser host (regents browser): each takes only its input, sends nothing with no signer or when the signer refuses, and sends exactly the bytes the signer signed, with the proof and no cookie
- Be known by one record per wallet, with the first World ID person it accepted kept for good
- Keep and read Model Climb reports only for its own person
- Get a funded Wallet Bench test's money back to the funder even when a money test fails
- Fund Wallet Bench tests without the funder ever sending more than the run's total, and settle a send whose outcome was lost from Base, where a lagging node can never make a send that landed look replaced
- Correct one judge check on a Wallet Bench test as its reviewer: only that check changes, the judge's reason stays after the reviewer's, the timeline gains one Reviewer correction entry however often it runs, and the test's page marks the check and counts it
- Sentinel's age of the oldest unconfirmed Wallet Bench payment: the oldest funding send still signed or unknown sets its age by flow, 0 when none waits, and a query that fails is logged and skipped; the test configuration names no query, so the site's poller never reads it there
- A browser that sends Global Privacy Control starts no visit: no `_visit` cookie, no visit on the page or on any call it makes (even one it sends itself), no arrival or step line, and its Sign in press still reaches the site
- A crowd's second of visit lines, 1,500 written at once, reaches the site's output whole, each line once, on a handler of their own; an ordinary line is written once, by the default handler; and the release image writes one JSON visit line for one request
- Call the hosted MCP server at `/mcp` with its own signature: admitted as that agent with no Techtree tools yet; a query string, a page from another site, a batch, a body that is not JSON, two credentials, any other method or address and a 121st request in a minute are refused in the site's shape
- With the Claude connector switched on, a person approves a connected app and pairs it from Pair New Agent; each app pairs on its own with its own code and wallet, a look-alike app or another account's token stays itself, only a check-in moves last contact, and off, the guide, pairing choice and agent-guide lines are gone
- Leave Techtree's team a private message under a topic, paired or not, and get its receipt, recorded as itself whatever the input says about the sender; the topic, text and reply_to are bounded and a refused message keeps nothing; each sender leaves 10 an hour and each address 30; only the site's admins read messages
- Its `operation_id` answers its first message again without using an allowance, also when another call kept it first, and refuses other text or another topic with `idempotency_conflict`
- `POST /api/v1/messages/{topic}` and the hosted tool `messages_leave` leave a message as the signed agent, answer a retry with the first receipt through either door, refuse bad input with `invalid_message` and its details, and count one address's 30 an hour together; an unsigned or forged request leaves nothing; the browser tool `messages_leave` has its host sign the message for its topic's address, with the topic out of the body, and asks for nothing without the UUID
- Claude's connector offers `messages_leave` once its app is paired with the agent permission, and not before
- With the connector on, Claude may connect by its published identity (`https://claude.ai/oauth/mcp-oauth-client-metadata`) instead of registering: discovery says `client_id_metadata_document_supported`, consent on this site reads and records the document, the code trades for tokens that work at `/mcp` and refresh, and only consent reads the address; one address may open consent 30 times a minute
- Use the `regents techtree` commands
- Ask Techtree's team for a job in one of the four lanes (`Techtree.Jobs`); only the team checks, quotes and refuses it, the quote gives the order a fresh payment reference, and only the asking agent, its paired person and the team read the order, its quote and its deposits; the agent or its person cancels before it is paid; no page, address, hosted tool or browser tool reaches these actions yet, and no material is uploaded with an order
- Pay a quoted order with two calls it signs itself, an approval on USDC then `depositUSDC` on REGENT revenue staking tagged `techtree.job` with the order's reference, from any wallet; one reader per chain and contract (`Techtree.Jobs.Reader`) reads Base at its newest block every five minutes, sooner when the agent or the team asks it to look now, and saves every such deposit once, exactly as first read, with no order when its reference matches none; the order is paid once its saved deposits reach the quote, stays quoted with less, ignores another tag, and expires only once the reader passes a block made after its expiry; a later deposit is recorded and changes nothing. Reading is off until a build sets `read_payments`; its first run reads back only 300 blocks from Base's newest block, so a deposit made longer ago, while reading was off, is never seen

## Repository

- Read the offer on the front page (`README.md`): the four services, the libraries each one uses grouped by maker with each one's status (Tested or Planned), the six steps, what to expect, the published example, and Book a call at the top and the end; then open each service's page in `factory/` for its steps with their status, what runs here today and the limits
- Read the release table, proof and privacy notes, and development setup in `docs/open-tools.md`, `docs/proof.md` and `docs/development.md`
