# Text to Audio

Type or upload text — get neural-quality mp3 audio from AWS Polly. Frontend on S3 + CloudFront, backend on Lambda + API Gateway.

**Live demo:** https://text-to-audio.jimmyhubbard2.cc

**Full documentation:** [PROJECT_MASTER.md](./PROJECT_MASTER.md) — architecture, AWS operational reference, build history, and key decisions

## Overview

Text to Audio sends text to AWS Polly via a Lambda proxy and plays the returned mp3 in the browser. Ten neural voices across English, Spanish, French, and German. Speed control (0.5×–2×) is applied as SSML `<prosody rate>`. The app is hardened with API key rate limiting at the gateway, a per-request character cap in the Lambda, and an AWS Budget alarm on Polly spend.

## Features

- **Ten neural voices** — Joanna / Matthew (en-US), Amy / Brian (en-GB), Lupe / Pedro (es-US), Andrés (es-MX), Lucia (es-ES), Léa (fr-FR), Vicki (de-DE)
- **.txt file upload** — drag-and-drop or browse; loads into the textarea
- **Direct text input** — paste up to 3,000 characters per request
- **Speed slider** — 0.5×–2×, applied via SSML `<prosody rate>` so playback speed is server-side, not just `<audio>` playback rate
- **Live char counter** — warns at 2,500, hard-blocks at 3,000
- **Stop button** — aborts an in-flight request *and* halts playback
- **Loading + playback states** — spinner during synthesis, animated wave during playback
- **No account, no signup** — just type and play

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Vanilla HTML5, CSS3, JavaScript |
| Frontend hosting | AWS S3 (private, OAC) + CloudFront |
| Backend | AWS Lambda (Python 3.12) + API Gateway (REST) |
| Speech synthesis | AWS Polly — neural engine, mp3 output |
| Cost control | AWS Budgets (Polly service, $5/mo alarm) |

No npm, no bundler, no framework, no external JS libraries.

## Architecture

```
Browser
   │  POST /synthesize
   │  body: { text, voiceId, rate }
   │  headers: x-api-key, Accept: audio/mpeg
   ▼
API Gateway (REST, prod stage)
   │  • API key required
   │  • Throttle: 10 rps / 20 burst
   │  • Quota: 1,000 requests/day
   │  • binary-media-types: audio/mpeg
   ▼
Lambda (Python 3.12)
   │  • Validates: text ≤ 3,000 chars, voiceId in allowlist, rate 20–200%
   │  • Wraps text in SSML <prosody rate="X%">
   │  • Calls polly.synthesize_speech(Engine="neural", OutputFormat="mp3")
   │  • Returns mp3 bytes as base64 with isBase64Encoded=true
   ▼
API Gateway decodes base64 → binary mp3 (via Accept: audio/mpeg)
   ▼
Browser plays via HTMLAudioElement + URL.createObjectURL(blob)
```

The frontend is served privately: the S3 bucket has BlockPublicAccess all-on, with a bucket policy scoped to the CloudFront distribution via OAC + SourceArn condition. There is no public S3 endpoint.

## Cost controls

Three layers:

1. **Lambda character cap** — requests with text length > 3,000 are rejected with HTTP 400. Polly is never called.
2. **API Gateway usage plan** — single API key with throttle (10 rps / 20 burst) and daily quota (1,000 requests). Without the key, requests are rejected with 403 at the gateway.
3. **AWS Budget alarm** — `text-to-audio-polly-monthly` filtered to the Polly service, $5/month limit, with email notifications at 80% forecast and 100% actual.

## Deployment

Frontend deploys automatically on push to `main` via GitHub Actions (`.github/workflows/deploy.yml`): S3 sync + CloudFront invalidation. Lambda code (`lambda_function.py`) is updated via the same workflow when the file changes.

**Frontend bucket:** `jimmy-text-to-audio` (us-east-1)
**Backend:** API Gateway + Lambda (us-east-1)

## Project structure

```
text-to-audio/
├── index.html          # Frontend — UI, fetch flow, playback
├── lambda_function.py  # Lambda handler — validation, Polly call, base64 mp3 response
└── .github/workflows/deploy.yml
```

## License

MIT — see [LICENSE](LICENSE)

## Author

Jimmy Hubbard — [github.com/jhubb88](https://github.com/jhubb88)
