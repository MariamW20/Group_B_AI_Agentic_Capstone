// src/routes/chat.js
import express from "express";
import { askGemini } from "../services/geminiService.js";

const router = express.Router();

// POST /api/chat  { "message": "How do I reset my online banking password?" }
router.post("/chat", async (req, res) => {
  const { message } = req.body;

  if (!message || typeof message !== "string" || !message.trim()) {
    return res.status(400).json({ error: "Field 'message' is required and must be text." });
  }

  try {
    const { text, latencyMs } = await askGemini(message);
    return res.json({ reply: text, latencyMs });
  } catch (err) {
    const statusCode = err.status === "rate_limited" ? 429 : err.status === "timeout" ? 504 : 502;
    return res.status(statusCode).json({ error: "Could not get a response from the model.", detail: err.status });
  }
});

export default router;
