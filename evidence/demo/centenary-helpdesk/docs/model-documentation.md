# Foundation Model Selection — Centenary Helpdesk Agent

## Model chosen: Google Gemini (`gemini-3.6-flash` via Gemini API / Google AI Studio)

### Why this model

We need a model that can (a) hold a helpdesk conversation, (b) later support tool/function
calling for ticket creation and status lookups (Week 4+), and (c) be free to run for the
duration of an 8-week student project with no billing risk. Gemini Flash satisfies all three
and has a generous no-cost tier for development-scale traffic.

### Capability

- Strong general instruction-following and summarization; good enough for grounded Q&A once
  RAG is added in Week 3.
- Native function/tool calling support — required for Week 4 tool integration (ticket lookup,
  ticket creation).
- Large context window (well beyond what a 10-50 document helpdesk corpus needs).
- Supports structured/JSON output, which we will use for tool-call arguments and for
  constraining the model to a fixed response schema in later weeks.

### Cost

- Free tier via Google AI Studio: no credit card required to obtain an API key.
- Free tier is rate-limited by requests-per-minute and requests-per-day rather than billed;
  sufficient for demo/evaluation traffic (30-scenario test set, in-class demo).
- Risk: if usage exceeds free-tier limits, requests are throttled/rejected (HTTP 429) rather
  than silently billed — acceptable for a student project with no payment method on file.

### Latency

- Flash-tier models are optimized for low latency versus larger "pro" variants; typical
  response time for a short helpdesk query is in the low single-digit seconds.
- We measure and log actual latency per request (see `geminiService.js`) so this can be
  reported with real numbers in the Week 2/8 reports rather than vendor claims.

### Privacy

- Requests leave our server and are sent to Google's API over HTTPS.
- Per course rule (Section 6, Rule 5): no confidential, personal or restricted institutional
  data will be sent. All helpdesk queries used for development/testing are synthetic or
  publicly available (per Section 3 use-case data constraints).
- API key is never committed to source control (`.env` is git-ignored; `.env.example` documents
  the required variable without a real value).

### Access

- Obtain a free API key at Google AI Studio (aistudio.google.com) — Google account required,
  no institutional approval needed since we use only synthetic/public data.
- Auth is via a single API key passed as a header/query param — no OAuth flow needed.
- No geographic restriction issues anticipated for use from Uganda at time of writing.

### Alternatives considered (for comparison)

| Model                  | Why not chosen (for now)                                                                                        |
| ---------------------- | --------------------------------------------------------------------------------------------------------------- |
| Groq (Llama models)    | Very low latency, also free tier — kept as fallback option if Gemini rate limits become a problem during demos. |
| OpenRouter free models | Free-tier open models, but less consistent function-calling support across models than Gemini.                  |
| OpenAI GPT models      | No free tier without billing setup; ruled out to avoid payment-method risk for a student project.               |

### Baseline test performed

See `src/services/geminiService.js` — a minimal wrapper that sends a single prompt and returns
the model's response, with basic error handling (timeout, empty response, rate-limit) and
latency logging. This is the "smallest useful model-backed capability" required before RAG
or tools are added.
