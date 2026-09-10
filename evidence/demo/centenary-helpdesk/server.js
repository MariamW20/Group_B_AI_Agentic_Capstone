// server.js — minimal example of wiring the chat route into an Express app.
// If you already have an Express app, just copy the two highlighted lines
// (import + app.use) into your existing server file instead of using this.
import "dotenv/config";
import express from "express";
import chatRoute from "./src/routes/chat.js"; // <-- add this to your existing app

const app = express();
app.use(express.json());

app.use("/api", chatRoute); // <-- and this

app.get("/", (req, res) => {
  res.send("Centenary Helpdesk API is running. POST /api/chat to talk to the model.");
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Server listening on port ${PORT}`));
