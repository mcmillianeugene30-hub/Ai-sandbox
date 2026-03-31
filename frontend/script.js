require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.43.0/min/vs' }});

let editor;
const elements = {
    provider: document.getElementById('provider-select'),
    model: document.getElementById('model-select'),
    apiKey: document.getElementById('api-key'),
    stream: document.getElementById('stream-toggle'),
    kb: document.getElementById('kb-toggle'),
    run: document.getElementById('run-btn'),
    compare: document.getElementById('compare-btn'),
    output: document.getElementById('output-content'),
    kbBtn: document.getElementById('kb-btn'),
    kbModal: document.getElementById('kb-modal'),
    kbStatus: document.getElementById('kb-status'),
    kbFile: document.getElementById('kb-file-input'),
    kbUpload: document.getElementById('kb-upload-btn'),
    singleView: document.getElementById('single-view'),
    compareView: document.getElementById('compare-view'),
    compProv: document.getElementById('compare-provider-select'),
    compModel: document.getElementById('compare-model-select'),
    outputA: document.getElementById('output-a'),
    outputB: document.getElementById('output-b')
};

const snippets = {
    gemini: `// AI Sandbox v3 - Gemini + RAG\nasync function main() {\n  const response = await ai.chat.complete({\n    messages: [{ role: 'user', content: 'What is the core theme of the document?' }],\n    stream: true,\n    kb_enabled: true // Enable context retrieval\n  });\n\n  for await (const chunk of response) {\n    process.stdout.write(chunk.choices[0].delta?.content || "");\n  }\n}\nmain();`,
    groq: `// AI Sandbox v3 - Groq Example\nasync function main() {\n  const response = await ai.chat.complete({\n    messages: [{ role: 'user', content: 'Summarize the document context.' }],\n    stream: true,\n    kb_enabled: true\n  });\n\n  for await (const chunk of response) {\n    process.stdout.write(chunk.choices[0].delta?.content || "");\n  }\n}\nmain();`,
    openrouter: `// AI Sandbox v3 - OpenRouter Example\nasync function main() {\n  const response = await ai.chat.complete({\n    messages: [{ role: 'user', content: 'Hi, compare your knowledge with the document.' }],\n    stream: true,\n    kb_enabled: true\n  });\n\n  for await (const chunk of response) {\n    process.stdout.write(chunk.choices[0].delta?.content || "");\n  }\n}\nmain();`,
    ollama: `// AI Sandbox v3 - Ollama Example\nasync function main() {\n  const response = await ai.chat.complete({\n    messages: [{ role: 'user', content: 'Why is the sky blue according to the doc?' }],\n    stream: true,\n    kb_enabled: true\n  });\n\n  for await (const chunk of response) {\n    process.stdout.write(chunk.choices[0].delta?.content || "");\n  }\n}\nmain();`
};

let compareMode = false;

async function loadModels() {
    try {
        const res = await fetch('http://localhost:8000/api/v1/models');
        const models = await res.json();
        
        function updateLists() {
            const p = elements.provider.value;
            elements.model.innerHTML = '';
            models[p].forEach(m => {
                const opt = document.createElement('option');
                opt.value = opt.textContent = m;
                elements.model.appendChild(opt);
            });
            editor.setValue(snippets[p] || snippets.gemini);

            // Update compare selects
            elements.compProv.innerHTML = '';
            Object.keys(models).forEach(prov => {
                const opt = document.createElement('option');
                opt.value = opt.textContent = prov;
                elements.compProv.appendChild(opt);
            });
            updateCompModelList(models);
        }

        function updateCompModelList(models) {
            const p = elements.compProv.value;
            elements.compModel.innerHTML = '';
            models[p].forEach(m => {
                const opt = document.createElement('option');
                opt.value = opt.textContent = m;
                elements.compModel.appendChild(opt);
            });
        }

        elements.provider.onchange = updateLists;
        elements.compProv.onchange = () => updateCompModelList(models);
        updateLists();
    } catch (err) {
        elements.output.textContent = "Error: Backend unreachable.";
    }
}

const ai = {
    chat: {
        complete: async (options, target = 'single') => {
            const provider = (target === 'single' || target === 'a') ? elements.provider.value : elements.compProv.value;
            const model = (target === 'single' || target === 'a') ? elements.model.value : elements.compModel.value;
            const apiKey = elements.apiKey.value;
            const stream = options.stream !== undefined ? options.stream : elements.stream.checked;
            const kb = options.kb_enabled !== undefined ? options.kb_enabled : elements.kb.checked;

            const res = await fetch('http://localhost:8000/api/v1/chat/completions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'x-api-key': apiKey },
                body: JSON.stringify({
                    provider, model, messages: options.messages,
                    temperature: 0.7, max_tokens: 1024, stream, kb_enabled: kb
                })
            });

            if (!res.ok) throw new Error((await res.json()).detail || 'Request Failed');

            if (stream) {
                const reader = res.body.getReader();
                const decoder = new TextDecoder();
                return {
                    [Symbol.asyncIterator]: async function* () {
                        let buf = "";
                        while (true) {
                            const { done, value } = await reader.read();
                            if (done) break;
                            buf += decoder.decode(value, { stream: true });
                            const lines = buf.split("\n");
                            buf = lines.pop();
                            for (const line of lines) {
                                if (line.startsWith("data: ")) yield JSON.parse(line.slice(6));
                            }
                        }
                    }
                };
            }
            return await res.json();
        }
    }
};

const process = {
    stdout: {
        write: (str, target = 'single') => {
            if (target === 'single') {
                elements.output.textContent += str;
                elements.output.scrollTop = elements.output.scrollHeight;
            } else {
                const out = target === 'a' ? elements.outputA : elements.outputB;
                out.textContent += str;
                out.scrollTop = out.scrollHeight;
            }
        }
    }
};

require(['vs/editor/editor.main'], () => {
    editor = monaco.editor.create(document.getElementById('editor-container'), {
        value: snippets.gemini, language: 'javascript', theme: 'vs-dark', automaticLayout: true
    });
    loadModels();
});

elements.run.onclick = async () => {
    if (compareMode) {
        elements.outputA.textContent = elements.outputB.textContent = "Running Comparison...\n";
        const code = editor.getValue();
        // Extract prompt from code - simplified for demo
        const messages = [{ role: 'user', content: 'Compare models for this prompt.' }];
        
        // Run parallel
        const runA = async () => {
            const res = await ai.chat.complete({ messages, stream: true }, 'a');
            for await (const c of res) process.stdout.write(c.choices[0].delta?.content || "", 'a');
        };
        const runB = async () => {
            const res = await ai.chat.complete({ messages, stream: true }, 'b');
            for await (const c of res) process.stdout.write(c.choices[0].delta?.content || "", 'b');
        };
        Promise.all([runA(), runB()]);
    } else {
        elements.output.textContent = "Running...\n";
        try {
            const fn = new Function('ai', 'process', `(async () => { ${editor.getValue()} })()`);
            await fn(ai, process);
        } catch (err) {
            process.stdout.write(`\n[ERROR] ${err.message}`);
        }
    }
};

elements.compare.onclick = () => {
    compareMode = !compareMode;
    elements.singleView.style.display = compareMode ? 'none' : 'flex';
    elements.compareView.style.display = compareMode ? 'flex' : 'none';
    elements.compare.textContent = compareMode ? 'Single Mode' : 'Compare Mode';
};

// KB Logic
elements.kbBtn.onclick = () => elements.kbModal.style.display = 'block';
document.querySelector('.close-kb').onclick = () => elements.kbModal.style.display = 'none';
elements.kbUpload.onclick = async () => {
    if (!elements.kbFile.files[0]) return;
    elements.kbStatus.textContent = "Uploading...";
    const formData = new FormData();
    formData.append('file', elements.kbFile.files[0]);
    try {
        const res = await fetch('http://localhost:8000/api/v1/kb/upload', { method: 'POST', body: formData });
        if (res.ok) elements.kbStatus.textContent = "Success! Document vectorized.";
        else elements.kbStatus.textContent = "Error uploading document.";
    } catch (e) { elements.kbStatus.textContent = "Connection error."; }
};
