# Setup — Gemini integration baseline

1. Get a free API key at https://aistudio.google.com (sign in with Google, click "Get API key").
2. `cp .env.example .env` and paste your key into `GEMINI_API_KEY`.
3. `npm install`
4. `npm start`
5. Test it:
   ```
   curl -X POST http://localhost:3000/api/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "How do I reset my online banking password?"}'
   ```
   You should get back `{ "reply": "...", "latencyMs": ... }`.

## If you already have an existing Express app
Don't run `server.js` — instead:
- Copy `src/services/geminiService.js` and `src/routes/chat.js` into your existing `src/` folder.
- In your existing server file, add:
  ```js
  const chatRoute = require("./src/routes/chat");
  app.use("/api", chatRoute);
  ```
- Make sure `express.json()` middleware is enabled and `.env` is loaded via `dotenv`.

## What this gives you for Week 2
- A working, tested model integration (Activity 2 ✅).
- `docs/model-documentation.md` — the capability/cost/latency/privacy/access writeup (Activity 1 ✅).
- Structured logs on every call (model, latency, status) — you'll want this evidence again in
  Week 7 for observability.

## What this does NOT do yet (on purpose)
- No retrieval/grounding (Week 3).
- No tools/function calling (Week 4).
- No versioned prompt spec beyond the one system instruction in `geminiService.js` — you still
  need to write the formal Prompt Specification v1.0 (role/task/context/constraints/output
  format/failure behaviour) as a separate Week 2 deliverable.
