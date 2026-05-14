# Text to Audio — Master Reference Document

*Operational reference + recruiter overview. Update when AWS resources change, after each phase, or when a key decision is revisited.*
*Last updated: 2026-05-14*

---

## 1. TL;DR

Type or upload text and get neural-quality mp3 audio from AWS Polly across ten voices in four languages. The backend ships with a three-layer cost guard — character cap at the Lambda, throttle and daily quota at API Gateway, and a $5/month AWS Budget alarm on Polly spend. Stack: single-file Python 3.12 Lambda (1.9 KB, IAM-auth only with no env vars), API Gateway with binary mp3 response, vanilla HTML/JS frontend on CloudFront + S3.

---

## 2. Live demo & repository

| Field | Value |
|---|---|
| Live URL | https://text-to-audio.jimmyhubbard2.cc |
| Repository | https://github.com/jhubb88/text-to-audio |
| Status | Working end-to-end (POST `/synthesize` → Polly → mp3 in browser) |
| Last frontend deploy | 2026-05-12 |
| Last Lambda deploy | 2026-05-10 (the rebuild commit) |
| CI trigger | Push to `main` (path-aware: Lambda only rebuilds when `lambda_function.py` changed) |

---

## 3. Architecture

The frontend posts `{text, voiceId, rate}` to `POST /synthesize` on API Gateway with `x-api-key` and `Accept: audio/mpeg`. API Gateway requires the key, rate-limits via usage plan `nnbuhq` (10 rps, 20 burst, 1000 per day), and proxies to Lambda. The Lambda validates (text ≤ 3000 characters, voiceId in a 10-voice allowlist, rate matching `^(\d{2,3})%$` between 20% and 200%), wraps the text in SSML `<prosody rate="X%">` with `xml.sax.saxutils.escape` for `<>&` safety, calls `polly.synthesize_speech(Engine="neural", OutputFormat="mp3")`, and returns the mp3 bytes as base64 with `isBase64Encoded=true`. API Gateway's `binaryMediaTypes: ["audio/mpeg"]` decodes the base64 back to binary on the response. The browser plays via `HTMLAudioElement` + `URL.createObjectURL(blob)`.

### Stack

| Layer | Technology |
|---|---|
| Frontend | Vanilla HTML5, CSS3, JS (single `index.html`, ~600 lines, inlined styles + scripts) |
| Hosting | S3 (`jimmy-text-to-audio`) + CloudFront (`E1BM7FLW1T9GAM`) |
| TLS | ACM cert, TLSv1.2_2021 minimum at CloudFront |
| API edge | API Gateway REST API `yhrh1k32ra`, stage `prod`, EDGE-optimized, `x-api-key` required |
| Compute | AWS Lambda `jimmy-text-to-audio` (python3.12, 128 MB, 30 s, 1957-byte single-file zip) |
| Polly auth | Lambda execution role only — no API key, no env var, no credential string |
| IAM scope | Inline `PollyAccess` policy with single allowed action `polly:SynthesizeSpeech` |
| Speech synthesis | AWS Polly — neural engine, mp3 output, 10 voices across en-US/en-GB/es-US/es-MX/es-ES/fr-FR/de-DE |
| Cost guards | Three layers — Lambda 3000-char cap, API Gateway 10 rps / 1000-day, AWS Budget $5/month on Polly |
| CI/CD | GitHub Actions on push to `main` — S3 sync, diff-guarded Lambda rebuild, CORS smoke test |
| License | MIT |

### Data flow

```
┌─────────┐  GET /          ┌────────────┐  GET *      ┌──────────────────┐
│ Browser │ ───────────────►│ CloudFront │ ──────────► │ S3 (frontend)    │
└────┬────┘                 │ E1BM7...   │             │ jimmy-text-to-...│
     │                      └────────────┘             └──────────────────┘
     │
     │ POST /synthesize  body: {text, voiceId, rate}
     │ headers: x-api-key + Accept: audio/mpeg
     ▼
┌────────────────────────┐  AWS_PROXY   ┌─────────────────────────────────┐
│  API Gateway           │ ───────────► │  Lambda (jimmy-text-to-audio)   │
│  yhrh1k32ra/prod       │              │  validate text/voice/rate       │
│  apiKey + 10 rps       │              │  SSML-wrap (prosody rate)       │
│  binaryMediaTypes:     │              │  polly.synthesize_speech()      │
│    audio/mpeg          │ ◄─── base64  │  return mp3 as base64           │
└─────────┬──────────────┘    audio/mpeg└─────────┬───────────────────────┘
          │                                       │
          │                                       │ IAM (no key, no env var)
          ▼                                       ▼
   APIGW decodes base64           ┌──────────────────────┐
   → binary mp3                   │  AWS Polly           │
          │                       │  neural / mp3        │
          ▼                       └──────────────────────┘
   Browser: blob URL → HTMLAudioElement → playback
```

---

## 4. Current state

### Works end-to-end

- POST text (≤ 3000 chars) and pick from 10 neural voices in 4 languages → get back mp3, played inline. Verified live 2026-05-12.
- Speed slider 0.5×-2× applied server-side via SSML `<prosody rate="X%">`, not just `<audio>` playbackRate.
- API key gating + throttle (10 rps / 20 burst) + daily quota (1000/day) at the gateway.
- AWS Budget `text-to-audio-polly-monthly` alarms at $5/month on Polly spend; currently $0.00 (HEALTHY).
- CI auto-deploys on push to `main`. Diff-guarded single-file Lambda rebuild + CORS smoke test.
- CORS `Access-Control-Allow-Origin` is scoped to the specific subdomain `https://text-to-audio.jimmyhubbard2.cc`, not the wildcard `*`. The only Lambda in the portfolio with origin-scoped CORS — see Key Decision 3.
- Lambda has zero environment variables. Polly authenticates via the execution role (single-action inline `polly:SynthesizeSpeech` policy).

### Open items

- Frontend calls the raw `execute-api.amazonaws.com` URL directly. No CloudFront proxy path. Tracked as E1.
- No operational CloudWatch alarms (Lambda errors, API Gateway 5xx). The AWS Budget alarm covers cost, not health. Tracked as E2.
- `portfolio-user` CLI principal lacks `cloudwatch:GetMetricStatistics` and `ce:GetCostAndUsage` permissions. Tracked as E3.
- Frontend bucket has no lifecycle configuration. Noncurrent versions accumulate; low impact at this traffic level. Not promoted to its own enhancement entry.

(Notably absent: no v4→v6 GitHub Actions enhancement — already shipped 2026-05-12. No "API key in client" gap — see Key Decision 3 for the intentional-design framing.)

---

## 5. Build history

### Phase 1 — Initial scaffold + favicons + docs (2026-04-14 → 2026-04-22)

Migrated from monorepo to a standalone repository (commit `9674db3`). The original implementation was browser-side Web Speech API — no Lambda, no API Gateway, no AWS Polly. Favicons added (`777f77f`). README + LICENSE + initial live demo link committed (`e159c38`).

### Phase 2 — CI/CD + subdomain wiring (2026-05-01 → 2026-05-07)

Deploy workflow added (`98db647`) for the Web Speech API era — at this point the workflow only synced the frontend to S3 and invalidated CloudFront, since there was no Lambda yet to deploy. Subdomain switched from the raw CloudFront URL to `text-to-audio.jimmyhubbard2.cc` via cPanel CNAME → CloudFront (`070b719`).

### Portfolio-wide infrastructure note — OAC migration (2026-05-07)

Frontend bucket `jimmy-text-to-audio` migrated to Origin Access Control as part of the portfolio-wide standardization across all eight project distributions. No source-code commit in this repo. See Key Decision 4.

### Phase 3 — Rebuild as real AWS Polly app (2026-05-10, commit `47f400f`)

Single commit replaced the browser-side Web Speech API implementation with the full Polly backend, hardened from day one. Everything below shipped in one shot:

- **`lambda_function.py` created** (4.2 KB source, 1.9 KB deployed). Validates text length ≤ 3000 chars, voiceId in a 10-voice allowlist (`Joanna`, `Matthew`, `Amy`, `Brian`, `Lupe`, `Pedro`, `Andres`, `Lucia`, `Lea`, `Vicki` across en-US/en-GB/es-US/es-MX/es-ES/fr-FR/de-DE), rate as `NN%` or `NNN%` between 20% and 200%. SSML wraps the text in `<prosody rate="X%">` with `xml.sax.saxutils.escape` for `<`, `>`, `&` safety. Returns mp3 bytes as base64 with `isBase64Encoded=true`.
- **IAM role `jimmy-text-to-audio-role`** with the inline policy `PollyAccess` — single allowed action `polly:SynthesizeSpeech`. No wildcard, no broader Polly access.
- **API Gateway `yhrh1k32ra`** with `binaryMediaTypes: ["audio/mpeg"]` so the base64 payload decodes to binary on response. POST `/synthesize` with `apiKeyRequired: true`. OPTIONS `/synthesize` for CORS preflight.
- **Usage plan `nnbuhq`** with throttle 10 rps / 20 burst and daily quota 1000.
- **CORS scoped to specific subdomain** (`https://text-to-audio.jimmyhubbard2.cc`) rather than `*`. See Key Decision 3.
- **AWS Budget `text-to-audio-polly-monthly`** at $5/month, filtered to the Polly service, with email notifications at 80% forecast and 100% actual.
- **Frontend rewrite** in the same commit: removed the Web Speech API code path entirely, added the `fetch(API_ENDPOINT, ...)` flow with `AbortController`, blob playback via `HTMLAudioElement` + `URL.createObjectURL(blob)`, busy-state guard so the Play button stays disabled during fetch + playback.

The IAM role, the cost guard, the CORS scoping, and the input validation all landed simultaneously with the working code — nothing deferred.

### Phase 4 — CORS smoke test + Lambda update wait + Node 24 bump (2026-05-12)

Two commits, same day. `e9abced` added the CORS smoke test (OPTIONS request against `/synthesize`, exits non-zero if `x-api-key` is missing from `Access-Control-Allow-Headers`) and an `aws lambda wait function-updated` step so the smoke test always sees the latest deploy. `21b3596` bumped `actions/checkout` and `aws-actions/configure-aws-credentials` from v4 to v6. text-to-audio is one of three portfolio projects already on v6 (the other two are resume-matcher and log-analyzer).

### Phase 5 — TLS audit (2026-05-14)

Audited reported TLS 1.0 on the REST API, traced it to AWS-managed edge enforcement, confirmed live floor is TLS 1.2+. No action required at the API Gateway layer; raw execute-api closure tracked as E1. Identical conclusion as the resume-matcher and log-analyzer audits.

---

## 6. Operational reference

### Lambda

| Field | Value |
|---|---|
| Function name | jimmy-text-to-audio |
| Runtime | python3.12 |
| Architecture | x86_64 |
| Handler | `lambda_function.lambda_handler` |
| Memory | 128 MB |
| Timeout | 30 s |
| Code size | 1,957 bytes (single-file deployment) |
| Last modified | 2026-05-10 |
| Role | `jimmy-text-to-audio-role` |
| Env vars | (none — Polly auth via IAM execution role only) |

### API Gateway

| Field | Value |
|---|---|
| API name | jimmy-text-to-audio-api |
| API ID | `yhrh1k32ra` |
| Type | EDGE-optimized REST |
| Stage | `prod` |
| Endpoint URL | https://yhrh1k32ra.execute-api.us-east-1.amazonaws.com/prod |
| `apiKeySource` | HEADER |
| `binaryMediaTypes` | `["audio/mpeg"]` (load-bearing — without this, the base64 mp3 won't decode to binary on response) |
| `disableExecuteApiEndpoint` | false (raw endpoint reachable; see E1) |
| `POST /synthesize` `apiKeyRequired` | true |
| `OPTIONS /synthesize` | open (preflight) |
| Integration | AWS_PROXY → Lambda `jimmy-text-to-audio` |
| Stage-level throttle | unset (uses usage plan) |
| Stage tracing | disabled |

### Usage plan

| Field | Value |
|---|---|
| ID | `nnbuhq` |
| Name | text-to-audio-portfolio-plan |
| Rate | 10.0 rps |
| Burst | 20 |
| Quota | 1,000 requests per day |
| Attached API stage | `yhrh1k32ra/prod` |
| API key | API key required; rotated via API Gateway console. The token embedded in the frontend is intentionally public — see Key Decision 3. |

### IAM

| Role | Type | Policy |
|---|---|---|
| jimmy-text-to-audio-role | AWS managed | `AWSLambdaBasicExecutionRole` |
| jimmy-text-to-audio-role | inline | `PollyAccess` (single allowed action: `polly:SynthesizeSpeech`) |

### S3 bucket

| Bucket | Purpose | PAB | Encryption | Lifecycle | Project tag |
|---|---|---|---|---|---|
| jimmy-text-to-audio | Static frontend | all 4 ON | AES256 | (none) | text-to-audio |

### CloudFront

| Field | Value |
|---|---|
| Distribution ID | `E1BM7FLW1T9GAM` |
| Status | Deployed |
| Aliases | `text-to-audio.jimmyhubbard2.cc` |
| CloudFront domain | `d2ey5cipu3t9y.cloudfront.net` |
| Origin | S3 REST endpoint → `jimmy-text-to-audio.s3.us-east-1.amazonaws.com` (OAC-fronted) |
| OAC ID | `EYZYRPB9J4ZFY` |
| Viewer cert source | ACM |
| ACM cert ARN | `arn:aws:acm:us-east-1:603509861186:certificate/598151c8-e0e7-4b46-acf0-4da54e5bce38` |
| Min protocol version | TLSv1.2_2021 |
| Price class | PriceClass_100 (NA + EU) |
| Custom error 403 → | `/index.html` (200) |
| Custom error 404 → | `/index.html` (200) |
| Default root object | `index.html` |
| WAF / WebACL | none |
| Cache behaviors | (DefaultCacheBehavior only) |

### CloudWatch alarms

None currently scoped to this project. Tracked as Future Enhancement E2.

### AWS Budget

| Field | Value |
|---|---|
| Budget name | `text-to-audio-polly-monthly` |
| Limit | $5.00 USD per MONTH |
| Cost filter | Service = Amazon Polly |
| Current actual spend | $0.00 |
| Health status | HEALTHY |
| Notifications | 80% forecast + 100% actual via email |

The portfolio's only shipped cost guard. Deliberately a Budget (cost protection) rather than a CloudWatch alarm (operational health) — see Key Decision 2.

### Cost & utilization

`portfolio-user` CLI principal does not have `cloudwatch:GetMetricStatistics` or `ce:GetCostAndUsage` permissions. 30-day Lambda invocation/error counts and per-project cost breakdowns are not queryable from the CLI right now. The `Project=text-to-audio` tag is present on every resource for Cost Explorer attribution, and the AWS Budget above provides actual Polly spend visibility through its own API. Tracked as E3.

---

## 7. Key decisions

### 1. Polly over Web Speech API

The original browser-side Web Speech API implementation shipped inconsistent voice quality across browsers, no consistent multilingual coverage, and depended on whether the user's specific browser had the right TTS voices installed. Polly delivers consistent neural voices across all browsers, an explicit selection of 10 voices in 4 languages, and mp3 output that any browser plays the same way. Trade-off: Polly costs per character and requires a network call, where Web Speech API was free and ran offline. For consistent voice quality across browsers and explicit multilingual support, the cost and network dependency are acceptable. The mitigation for the cost dimension is the three-layer cost guard (Decision 2), which caps spend at $5/month before the Budget alarm fires. The rebuild was a single-commit replacement (`47f400f`, 2026-05-10).

### 2. Three-layer cost guard

Three layers, each with concrete numbers:

- **Layer 1 — Lambda character cap.** Text > 3000 characters is rejected with HTTP 400 at the handler. Polly is never called for oversized input.
- **Layer 2 — API Gateway throttle and quota.** Usage plan `nnbuhq` enforces 10 rps / 20 burst at the per-second level and 1000 requests per day at the daily level. Without the rate-limit token, requests are rejected at the gateway with HTTP 403.
- **Layer 3 — AWS Budget.** `text-to-audio-polly-monthly` alarms at $5/month on Polly service spend, with email notifications at 80% forecast and 100% actual.

Combined effect: a runaway demo or attack would hit the daily quota (1000 requests) well before reaching the $5/month threshold. The Budget alarm is the backstop, not the first line of defense.

### 3. Public rate-limit token vs hidden secret (network-layer discipline cluster)

The frontend embeds a literal `RATE_LIMIT_TOKEN` in `index.html` line 428. The inline comment at lines 424-426 documents the design intent verbatim:

> RATE_LIMIT_TOKEN is a public-side rate-limit token, NOT a secret. It enforces throttle (10 rps / 20 burst) and quota (1000/day) at API Gateway. Embedding it in the page is the intended design.

The distinction matters: an authentication token must be hidden because it grants access. A rate-limit identifier tells the API Gateway which usage plan to bill against — embedding it in client code is fine because the worst-case abuse is consuming the quota, which is exactly what the quota is for.

Related network-layer discipline that ships in the same Lambda: the CORS response sets `Access-Control-Allow-Origin` to the specific subdomain `https://text-to-audio.jimmyhubbard2.cc`, not the wildcard `*`. Browsers running on any other origin get CORS-rejected before the Lambda processes the request. Most other portfolio Lambdas use `*`; this one is the exception.

Together: the gateway authenticates the client (key → usage plan), the gateway throttles the client (10 rps), the daily quota caps total exposure (1000/day), and the Lambda CORS response prevents drive-by abuse from other origins.

### 4. OAC over OAI for the static-site bucket

Standard portfolio-wide OAC justification. Bucket policy scoped to `cloudfront.amazonaws.com` service principal with a `SourceArn` condition pinned to distribution `E1BM7FLW1T9GAM`; CloudFront can read, nothing else can. All four Public Access Block settings on. Static website hosting disabled (S3 REST endpoint via OAC). SPA-style routing handled at CloudFront with `CustomErrorResponses` mapping 403 and 404 to `/index.html` with a 200 response. OAC is the AWS-recommended pattern since 2022. Migrated 2026-05-07 as part of the portfolio-wide OAC standardization.

### 5. TLS hardening — accepted AWS-managed edge enforcement (2026-05-14)

The `securityPolicy: TLS_1_0` reported by `get-rest-api` looked alarming at first read. EDGE-optimized REST APIs without a custom domain route through an AWS-managed CloudFront layer, and the `securityPolicy` field on the REST API itself is informational unless bound to a custom domain name. No custom domain exists for this API (`aws apigateway get-domain-names` returned `[]`), so the field is vestigial and the live TLS floor for traffic to `https://yhrh1k32ra.execute-api.us-east-1.amazonaws.com` is set by AWS at TLS 1.2+. No action taken at the API Gateway layer. The meaningful follow-up is closing the raw execute-api endpoint and forcing all traffic through CloudFront; tracked as Future Enhancement E1.

---

## 8. Future enhancements

### E1 — Close the raw execute-api endpoint (priority: medium)

The frontend currently posts directly to `https://yhrh1k32ra.execute-api.us-east-1.amazonaws.com/prod/synthesize`. This works but bypasses CloudFront entirely: no edge attachment point for WAF, no single TLS chokepoint, no edge caching surface. Two paths forward:

- **Path A — CloudFront `/api/*` behavior.** Add a second origin to distribution `E1BM7FLW1T9GAM` pointing at `yhrh1k32ra.execute-api.us-east-1.amazonaws.com`. Add a cache behavior with path pattern `/api/*` targeting the new origin, `AllowedMethods` including POST + OPTIONS, no caching of POST. Rewrite `API_ENDPOINT` in `index.html` line 427 from the raw URL to `'/api/synthesize'`. Update the CORS smoke test in `.github/workflows/deploy.yml` line 61 to hit the CloudFront-proxied path.
- **Path B — API Gateway custom domain.** Provision `api.text-to-audio.jimmyhubbard2.cc` as a custom domain, attach ACM cert, map to API `yhrh1k32ra` stage `prod`. Set TLS policy `TLS_1_2`. Rewrite `API_ENDPOINT` in `index.html` line 427 to the new custom domain.

Either path eliminates the raw endpoint as a network reach surface. After either lands, set `disableExecuteApiEndpoint=true` and redeploy the prod stage.

### E2 — Operational CloudWatch alarms for Lambda errors and APIGW 5xx (priority: medium)

The AWS Budget alarm covers cost, but no alarms exist for operational health. Suggested baseline:

- Lambda `Errors >= 3 in 5 min` on the `jimmy-text-to-audio` function (catches Polly outages, IAM permission drift, panic in the handler).
- API Gateway `5XXError >= 5 in 5 min` on the `yhrh1k32ra/prod` stage (catches integration failures and Lambda invocation errors that surface as 502/504).

SNS topic with email subscription. One-time setup, low ongoing maintenance. Distinct from Decision 2's cost guard — this covers reliability, not bill prevention.

### E3 — Grant `portfolio-user` CLI observability reads (priority: low)

Same enhancement carried over from the other portfolio PROJECT_MASTERs. `cloudwatch:GetMetricStatistics` and `ce:GetCostAndUsage` both return AccessDenied for the `portfolio-user` IAM principal. Today this means scripted observability reads fall back to the AWS Console or to per-service APIs (e.g., the AWS Budgets API for Polly spend). Granting either inline or via attached managed policies (`CloudWatchReadOnlyAccess` plus a Cost Explorer policy) unblocks scripted observability across all portfolio projects at once.

### E4 — End-to-end test in CI (priority: medium)

CI today verifies CORS preflight but not the full POST → 200 → mp3 response loop. A synthetic short text + one of the 10 voices + a real POST + a check that the response body decodes as valid mp3 (or at least starts with the mp3 magic bytes `\xFF\xFB` or `\xFF\xF3`) would catch regressions in Lambda integration, Polly behavior, and API Gateway's binary-media-type handling — silent failure modes the CORS smoke test cannot reach. Cost: one Polly call per CI run, well under the $5/month Budget.

---

## 9. Files & structure

```
text-to-audio/                         ← Lives on Windows Desktop
├── .github/
│   └── workflows/
│       └── deploy.yml                 ← CI/CD — S3 sync, diff-guarded Lambda rebuild, CORS smoke (80 lines, on v6 majors)
├── LICENSE                            MIT
├── README.md                          Recruiter-facing summary (~92 lines, includes ASCII architecture)
├── index.html                         Frontend — UI, fetch flow, blob playback (~600 lines)
├── lambda_function.py                 Handler — validation, Polly call, base64 mp3 (128 lines)
├── deploy.sh                          One-shot infra deploy script (retained)
├── apple-touch-icon.png
├── favicon-16.png
├── favicon-32.png
├── favicon.ico
├── icon-192.png
└── icon-512.png
```
