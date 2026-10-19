# Techtree one-purpose mockups

Static mockups of techtree.sh split into pages that each do one job, so every
address can be shared as "try this link, it lets you do X". They reuse the live
site's stylesheet, fonts, crown and shared footer. Nothing here changes the
Techtree code.

## Pages

| Address | What it is |
| --- | --- |
| `/` | New home page: find out if your Skill really helps your agent. One line to paste into your agent, a three-step "How it works", and links to every other page. |
| `/docs/` | Docs index: "What do you want to do?" Eleven guides in three groups, each with its own address. |
| `/docs/test-a-skill/` | One guide, as the pattern for the rest: three steps with copyable commands, Copy link, and Next. |
| `/page-list/` | Every proposed page with its one job and what changes, plus desktop and phone pictures in light and dark. |

## Run it

```sh
node build.mjs   # writes site/ from src/layout.html and src/pages/
node serve.mjs   # serves site/ at http://localhost:4015/
```

Edit pages in `src/pages/`, then rebuild. Styling for the mockups lives in
`site/assets/css/mockup.css`; behaviour (theme switch, crown, copy buttons,
button motion) in `site/assets/js/mockup.js`.

## Checks

```sh
npm install                          # once: installs Playwright
npx playwright install chromium      # once, if Chromium is not installed yet
node check.mjs           # headless checks
node check.mjs --shots   # same, and retakes the six pictures in site/page-list/shots/
```

Needs the server running. Covers every page at
desktop, phone and 320px widths in light and dark: no sideways scrolling, no
console errors, no failed loads, the crown draws or shows its still picture,
the footer is present, every internal link and anchor lands, the theme switch,
Copy and Copy link, the hover arrow and press, and reduced motion.
