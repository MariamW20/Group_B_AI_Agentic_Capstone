// src/services/geminiService.js
//
// Minimal, testable wrapper around the Gemini API for the Week 2 baseline.
// No RAG, no tools yet — just: prompt in, model response out, with basic
// error handling and latency measurement so we have real numbers to report.
//
// Uses the current official SDK: @google/genai (the old @google/generative-ai
// package is end-of-life as of late 2025).

import { GoogleGenAI } from "@google/genai";

if (!process.env.GEMINI_API_KEY) {
  throw new Error(
    "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key."
  );
}

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });
const MODEL_NAME = process.env.GEMINI_MODEL || "gemini-3.6-flash";

// Baseline system instruction (this is "Prompt Specification v1.0" territory —
// you'll formalize this further later this week per the assignment).
const SYSTEM_PROMPT = `You are a helpdesk assistant for Centenary Bank/University customers
(adjust to your actual chosen org). Answer clearly and concisely.
If you do not know something with confidence, say so explicitly instead of guessing.
Do not invent account numbers, case statuses, or policy details — those will be grounded
by retrieval/tools added in later weeks.`;

/**
 * Send a single user message to Gemini and return the text response.
 * @param {string} userMessage
 * @returns {Promise<{text: string, latencyMs: number}>}
 */
export async function askGemini(userMessage) {
  if (!userMessage || typeof userMessage !== "string" || !userMessage.trim()) {
    throw new Error("userMessage must be a non-empty string");
  }

  const start = Date.now();
  const timeoutMs = 15000;

  try {
    const result = await Promise.race([
      ai.models.generateContent({
        model: MODEL_NAME,
        contents: userMessage,
        config: { systemInstruction: SYSTEM_PROMPT },
      }),
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error("TIMEOUT")), timeoutMs)
      ),
    ]);

    const latencyMs = Date.now() - start;
    const text = result.text;

    if (!text || !text.trim()) {
      throw new Error("EMPTY_RESPONSE");
    }

    // Log for the evaluation/observability evidence you'll need later.
    console.log(
      JSON.stringify({
        event: "gemini_call",
        model: MODEL_NAME,
        latencyMs,
        inputChars: userMessage.length,
        outputChars: text.length,
        status: "ok",
      })
    );

    return { text, latencyMs };
  } catch (err) {
    const latencyMs = Date.now() - start;
    const status =
      err.message === "TIMEOUT"
        ? "timeout"
        : err.message === "EMPTY_RESPONSE"
        ? "empty_response"
        : err?.status === 429
        ? "rate_limited"
        : "error";

    console.error(
      JSON.stringify({
        event: "gemini_call",
        model: MODEL_NAME,
        latencyMs,
        status,
        error: err.message,
      })
    );

    const wrapped = new Error(`Gemini call failed: ${status}`);
    wrapped.status = status;
    throw wrapped;
  }
}
