# Fonts

Self-hosted so the Content Security Policy (`default-src 'self'`) needs no
third-party origin and no student request reaches a font CDN. Each file is the
Latin subset served by Google Fonts (covers Italian accents and curly quotes);
other characters fall back to the system stacks in `css/style.css`.

| File | Family | Weights | Role | License |
| --- | --- | --- | --- | --- |
| `atkinson-hyperlegible-next-latin.woff2` | Atkinson Hyperlegible Next (variable) | 400–700 | Body and UI text | `OFL-atkinson-hyperlegible-next.txt` |
| `bricolage-grotesque-800-latin.woff2` | Bricolage Grotesque (opsz 48) | 800 | Headings | `OFL-bricolage-grotesque.txt` |
| `atkinson-hyperlegible-mono-500-latin.woff2` | Atkinson Hyperlegible Mono | 500 | Code snippets only | `OFL-atkinson-hyperlegible-mono.txt` |

All three are licensed under the SIL Open Font License 1.1.
