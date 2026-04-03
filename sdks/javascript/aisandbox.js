class AISandboxClient {
    constructor(config = { baseUrl: "https://nexus-backend-ffn4.onrender.com", apiKey: "" }) {
        this.baseUrl = config.baseUrl || "https://nexus-backend-ffn4.onrender.com";
        this.apiKey = config.apiKey || "";
        this.chat = new Chat(this);
    }
}

class Chat {
    constructor(client) {
        this.client = client;
    }

    async completions(provider, model, messages, options = {}) {
        const stream = options.stream || false;
        const url = `${this.client.baseUrl}/api/v1/chat/completions`;
        const headers = {
            "Content-Type": "application/json",
            "x-api-key": this.client.apiKey
        };
        const body = JSON.stringify({
            provider: provider,
            model: model,
            messages: messages,
            ...options
        });

        const response = await fetch(url, {
            method: 'POST',
            headers,
            body
        });

        if (!response.ok) {
            const errText = await response.text();
            throw new Error(`AI Sandbox Error: ${errText}`);
        }

        if (stream) {
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            return {
                [Symbol.asyncIterator]: async function* () {
                    let buffer = "";
                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;
                        buffer += decoder.decode(value, { stream: true });
                        const lines = buffer.split("\n");
                        buffer = lines.pop();
                        for (const line of lines) {
                            if (line.startsWith("data: ")) {
                                try {
                                    yield JSON.parse(line.slice(6));
                                } catch (e) {
                                    console.error("Failed to parse SSE line", line);
                                }
                            }
                        }
                    }
                }
            };
        }

        return await response.json();
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = AISandboxClient;
} else {
    window.AISandboxClient = AISandboxClient;
}
