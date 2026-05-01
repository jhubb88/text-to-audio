# Text to Audio

Browser-based text-to-speech tool — upload a .txt file or paste text, choose a voice, and play.

**Live demo:** https://d2ey5cipu3t9y.cloudfront.net

## Overview

Text to Audio converts plain text to spoken audio using the browser's built-in Web Speech API. No server, no API keys, no file uploads to a third party — synthesis runs entirely on the client. Voices are sourced from the operating system and vary by browser and platform.

## Features

- **.txt file upload** — drag-and-drop or browse; file contents load into the text area automatically
- **Direct text input** — type or paste text into the text area
- **Voice selector** — populated from available browser/OS voices with language tags
- **Speed control** — rate slider from 0.5× to 2×
- **Pitch control** — pitch slider from 0.5 to 2.0
- **Play / Stop** — cancel synthesis at any time; animated wave indicator while speaking
- Works in Chrome, Edge, Safari, and Firefox (voice availability varies by platform)

## Tech stack

| Layer | Technology |
|---|---|
| Markup / style / logic | Vanilla HTML5, CSS3, JavaScript |
| Speech synthesis | Web Speech API (browser built-in) |
| Fonts | Google Fonts (Inter) |
| Hosting | AWS S3 + CloudFront |

No npm, no bundler, no framework, no external JS libraries.

## Local development

```bash
python3 -m http.server 8080
```

Open `http://localhost:8080`. No build step, no dependencies to install.

## Deployment

Deploys automatically on push to main via GitHub Actions (.github/workflows/deploy.yml). S3 + CloudFront invalidation handled by the workflow.

**S3 bucket:** `jimmy-text-to-audio` (us-east-1)

## Project structure

```
text-to-audio/
└── index.html      # Complete application — HTML, CSS, and JS in one file
```

## License

MIT — see [LICENSE](LICENSE)

## Author

Jimmy Hubbard — [github.com/jhubb88](https://github.com/jhubb88)

---

*Part of [jhubb88's portfolio](https://jimmyhubbard2.cc)*
