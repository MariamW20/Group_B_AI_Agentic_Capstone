// Evaluate grounded prompts using the existing SDK and local credentials.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import dotenv from 'dotenv';
import { GoogleGenAI } from '@google/genai';
const here = path.dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: path.join(here, '.env') });
const tracePath = path.resolve(here, '../../traces/rag-evaluation.json');
const report = JSON.parse(fs.readFileSync(tracePath, 'utf8'));
const model = process.env.GEMINI_MODEL || 'gemini-3.6-flash';
report.generation_model = model;
const ai = process.env.GEMINI_API_KEY ? new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY }) : null;
for (const row of report.results) {
  const start = Date.now();
  try {
    if (!ai) throw Object.assign(new Error('Missing API key'), {status: 'MISSING_API_KEY'});
    const response = await ai.models.generateContent({model,
      contents: row.messages[1].content,
      config: {systemInstruction: row.messages[0].content, temperature: 0,
        httpOptions: {timeout: 45000}}});
    if (!response.text?.trim()) throw Object.assign(new Error('Empty response'), {status: 'EMPTY_RESPONSE'});
    row.actual_answer = response.text;
    row.generation_status = 'OK';
  } catch (error) {
    row.generation_status = 'BLOCKED';
    row.generation_error = String(error.status || error.code || 'NETWORK_OR_API_ERROR');
  }
  row.generation_latency_ms = Date.now() - start;
  fs.writeFileSync(tracePath, JSON.stringify(report, null, 2) + '\n');
  console.log(row.id, row.generation_status, row.generation_error || '', row.generation_latency_ms);
}
