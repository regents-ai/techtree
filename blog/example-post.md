---
title: "Your first blog post"
description: "An unpublished authoring example with headings, images, code, tables and LaTeX."
date: "2026-09-08"
author: "Example Author"
author_x: "https://x.com/example"
image: "/images/blog/example-cover.svg"
image_alt: "A geometric cover image for an unpublished example post"
draft: true
---

This is an **unpublished template**, not an announcement. Replace the front matter,
cover image and text, then set `draft: false` to publish after the next build.

## A clear opening

Start with the idea, then explain why it matters. Use [descriptive links](/blog),
*emphasis*, and a comfortable reading rhythm.

### Supporting details

- Keep one idea per paragraph.
- Use meaningful headings; they become the table of contents.
- Store images in `blog/images/` and reference `/images/blog/filename.svg`.

> A useful quotation or aside belongs in a blockquote.

## Equations

Inline LaTeX works as $E = mc^2$. Display equations use their own lines:

$$
\mathcal{L}(\theta) = -\frac{1}{N}\sum_{i=1}^{N}\log p_\theta(y_i \mid x_i)
$$

Escape literal currency dollar signs: \$25. Mathematics is rendered locally,
with a readable TeX fallback if JavaScript is unavailable.

## Code and tables

```elixir
Enum.map(posts, & &1.title)
```

| Field | Purpose |
| --- | --- |
| `title` | The article heading and gallery label |
| `date` | The publication date, newest first |
| `draft` | Keep unfinished work out of public routes |

## A closing thought

Give the reader a concrete conclusion. Footnotes work too.[^note]

[^note]: This entire example stays unpublished until you deliberately change its front matter.
