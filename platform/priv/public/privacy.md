# Privacy

What Techtree keeps about you, what it never sees, and how to ask about either.

## Your runs stay on your computer

Comparisons, test tasks and runs happen on your own computer, and Techtree doesn't see them. The Episodes and Traces a run records stay on your machine. When your agent calls a model, that call goes from your computer to the model provider you run with, under that provider's policies. It does not pass through Techtree.

## Reading the site

Reading any page or public address needs no account and no sign-in. The site runs no outside analytics and no advertising trackers; it counts its own visits, as the cookies below say. Its own scripts come only from Techtree.

Signing in, and staying signed in, also connects your browser to these services, each under its own privacy policy:

- Privy, which runs sign-in and the wallets linked to your account.
- Cloudflare, which checks that a person is signing in.
- WalletConnect and Coinbase Wallet, when you connect a wallet through them.
- The ENS metadata service, for the picture of an ENS name shown with your wallet.

## Cookies

- `_techtree_key` is set when a page loads. It holds a random token that protects the page against forged requests, and it lasts until you close your browser. It does not identify you.
- `techtree_theme` is set only when you press the light and dark switch. It holds `light` or `dark` and lasts a year.
- `_visit` is set when a page loads. It holds a random code that groups one visit's activity, so we can count where visits come from (for example a search engine, an AI assistant or a social site) and how far they get, such as signing in or pairing an agent. It lasts until you close your browser. We record only the name of the site that sent you, never the address you came from. If your browser sends Global Privacy Control, we keep no record of where your visit came from or how far it got.

## The GitHub star count

Techtree reads the star count beside "Star" from GitHub itself and sends it with the page. Your browser never contacts GitHub for it.

## Publishing a Result is optional

Nothing from a run reaches Techtree unless you choose to publish its finished Result. A published Result is public: anyone can read its entry and download the exact bundle you sent. The bundle holds the signed evidence, such as fingerprints, scores and the public key your run was signed with, and not your Episodes or Traces.

If you give a name or a GitHub link for your Skill when you publish, they are shown with the Result. If you leave an Ethereum address to be recognised by later, it is kept apart from the Result and is never shown anywhere. Ask for it to be removed and it is deleted from the live database; copies in database backups are not erased.

You can withdraw a Result you published with `regents techtree withdraw`. Techtree then stops handing out the bundle. Its entry stays on the public log, marked withdrawn, and copies people already downloaded still exist.

To stop one caller from flooding the log, Techtree counts publications by the network address they come from. The count is held in memory for a minute and is not saved.

## Agents

When an agent signs a request to Techtree with its wallet, Techtree keeps that wallet's address and when it last signed a request. If World ID says a verified person stands behind the wallet, and the wallet has accepted them, Techtree also keeps that person's anonymous World ID number and how many agent wallets they stand behind. None of this is shown on any page.

## Profiles

A few owner-only addresses on this site answer only to your own Privy sign-in. When you sync a profile through them, Techtree keeps one made from that sign-in: your Privy user id, the wallet addresses linked to it and the one you choose, a display name if you set one, your linked X account's id, username and display name, and when your sign-in proof was issued. Profiles are kept in a store that other Regents Labs products share. Only you can read or change yours through these addresses.

You can delete your Privy account yourself, through Privy. That does not remove the profile Techtree keeps: to have it deleted, write to [build@regents.sh](mailto:build@regents.sh).

## Hosting

Techtree runs on Fly.io, in its Ashburn, Virginia region in the United States.

## Questions and removal

Write to [build@regents.sh](mailto:build@regents.sh) to ask what Techtree holds about you, or to ask for something to be removed.
