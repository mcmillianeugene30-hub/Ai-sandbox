# AI Sandbox Environment & SDK Platform v2.0

A high-performance, developer-centric sandbox for building AI-powered **Web and Mobile** applications.

## 🚀 New in v2.0

- **Streaming Support (SSE):** Real-time token streaming for all providers (Gemini, Groq, OpenRouter, Ollama).
- **Local AI Integration (Ollama):** Run and test models locally (e.g., Llama3, Mistral) without API costs.
- **Usage Analytics Dashboard:** Track average latency and request counts per provider/model.
- **Code Export:** One-click export of production-ready **React Hooks** and **Flutter Service** snippets.
- **Enhanced SDKs:** Both Python and JavaScript SDKs now natively support async streaming iterators.

## 📁 Project Structure

```text
/workspace/ai-sandbox/
├── backend/            # Python FastAPI backend (v2 with SSE & SQLite)
│   ├── main.py         
│   ├── providers.py    
│   ├── usage.db        # SQLite database for analytics
│   └── requirements.txt
├── frontend/           # Custom Playground v2.0
│   ├── index.html      # UI with Analytics & Code Export
│   ├── script.js       # Streaming & Mock SDK logic
│   └── style.css
└── sdks/               
    ├── python/         # Python SDK (Supports Streaming)
    └── javascript/     # JS SDK (Supports Async Iterators)
```

## 🛠️ Advanced Usage

### Streaming with JavaScript SDK
```javascript
const stream = await client.chat.completions('groq', 'llama-3.3-70b-versatile', messages, { stream: true });

for await (const chunk of stream) {
  process.stdout.write(chunk.choices[0].delta?.content || "");
}
```

### Local Development with Ollama
1. Ensure Ollama is running on `localhost:11434`.
2. Select **Ollama** in the Sandbox dropdown.
3. No API key required for local testing.

### Analytics & Monitoring
Click the **Analytics** button in the header to view performance metrics. This helps mobile developers choose the fastest models for low-latency user experiences.

---
Built with ❤️ by Skywork Agent

