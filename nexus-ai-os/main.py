import sys
import os

# Get the current directory of this file
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from core.kernel import NexusKernel
from agents.coder import CoderAgent

def main():
    kernel = NexusKernel()
    coder = CoderAgent(kernel)
    
    # Task for the agent
    task = "Write a Python script that calculates the 10th Fibonacci number and saves it to 'fib_result.txt'."
    provider = "ollama"
    model = "llama3"
    
    # Use the Groq API Key from the environment
    api_key = os.getenv("GROQ_API_KEY")
    
    try:
        result = coder.self_correct(task, provider, model, api_key=api_key)
        print(f"🏁 Final Agent Output: {result}")
        
        # Verify result
        if os.path.exists("fib_result.txt"):
            with open("fib_result.txt", "r") as f:
                print(f"📄 Content of fib_result.txt: {f.read()}")
    except Exception as e:
        print(f"❌ Kernel/Agent Error: {str(e)}")

if __name__ == "__main__":
    main()
