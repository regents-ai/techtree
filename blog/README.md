# Writing a blog post

This folder owns this site's blog content. `platform/` renders `/blog` and
`/blog/<slug>` using the shared `regent_blog` catalog and `Regent.Blog` components.
No database, CMS, React runtime or browser Markdown fetch is involved.

## Publish

1. Copy `example-post.md` to a lowercase hyphenated name such as `a-clear-title.md`.
2. Replace the title, description, date, author and author's X profile URL.
3. Put a cover image in `blog/images/`; reference `/images/blog/your-cover.webp` and
   write useful `image_alt` text. Use same-origin image paths in the body too.
4. Write the article below the closing `---`. Keep `draft: true` until ready.
5. Set `draft: false`, then run `mix assets.build` from `platform/` and refresh.
   Production changes appear after the usual reviewed release, not from editing a live server.

```yaml
---
title: "A clear article title"
description: "A short gallery description."
date: "2026-09-08"
author: "Your name"
author_x: "https://x.com/your_handle"
image: "/images/blog/your-cover.webp"
image_alt: "Describe the useful content of the cover"
draft: true
---
```

- Required: `title`, ISO `date`, `author`, full HTTPS `author_x`, `image`, `image_alt`.
- Optional: `description`, `draft` (defaults to false), `slug` (defaults to the filename).
- Slugs use lowercase ASCII letters/digits and single hyphens. They must be unique.
- Public posts are ordered by publication date descending, then slug for same-day ties.
- Drafts and posts dated after today's **UTC** date return 404 and never enter the gallery.
- `README.md` is documentation and is not a post. Only root-level `*.md` files are posts.
- Invalid metadata and duplicate slugs fail the build rather than silently dropping content.
- Markdown changes are compile-time inputs; a development refresh recompiles changed,
  added or deleted posts. Restart an already-running dev server after adding this dependency.
- Images are public build assets, even when only referenced by a draft. Never store private
  files in `images/`. Raw Markdown is not copied to `priv/static`.

## Markdown and LaTeX

Use `##` sections and `###` subsections for the automatically generated table of
contents. Duplicate headings receive unique anchors. Lists, emphasis, blockquotes,
links, code fences, tables and footnotes are supported. A body `#` is normalized
to a section heading so the article title remains the one page H1.

Inline math: `$E = mc^2$`. Display math: `$$` on separate lines around the equation.
Escape currency dollar signs as `\$25`. KaTeX-supported math is rendered from a
local module into accessible MathML; arbitrary LaTeX packages are not supported.
Code blocks do not become math. Without JavaScript, the TeX remains readable and
all contents links still work. Raw HTML and HEEx are not executed.

Desktop gets a sticky, scrollable contents rail and active-section indicator.
Narrow layouts get an expandable contents list above the article. Site colors,
header, fonts and the light/dark control remain owned by the product.

## Build inputs

The catalog is compiled into the application, so a release does not read this
source folder at runtime. `mix regent_blog.assets` stages `images/` and the local
math module as part of both `mix assets.build` and `mix assets.deploy`.

The shared package is `repos/elixir-utils/blog`; choose it with `REGENT_BLOG_PATH`
when using a pinned dependency snapshot. Shared UI requires the matching blog
components in `regent_ui`. Commit/review shared work first, then advance consumer
CI/release pins to those actual commits; do not invent a future revision.

Before the application-only Docker build, run `mix regent_blog.stage` alongside
existing shared dependency staging. It requires the pinned elixir-utils snapshot
and its exact `REGENT_BLOG_REVISION`. Generated `platform/vendor/regent_blog` and
`platform/vendor/regent_blog_content` are build inputs, not checked-in copies.
