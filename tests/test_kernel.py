import pytest
from core.kernel import NexusKernel

def test_extract_code_basic():
    kernel = NexusKernel()
    text = "Here is your code:\n```python\nprint('hello')\n```\nHope it works!"
    code = kernel.extract_code(text)
    assert code == "print('hello')"

def test_extract_code_no_lang():
    kernel = NexusKernel()
    text = "```\nls -la\n```"
    code = kernel.extract_code(text, language="")
    assert code == "ls -la"

def test_extract_json_block():
    kernel = NexusKernel()
    text = "Result:\n```json\n{\"status\": \"ok\", \"val\": 123}\n```"
    data = kernel.extract_json(text)
    assert data["status"] == "ok"
    assert data["val"] == 123

def test_extract_json_raw():
    kernel = NexusKernel()
    text = "Just some text and {\"key\": \"value\"} in the middle."
    data = kernel.extract_json(text)
    assert data["key"] == "value"

def test_extract_json_invalid():
    kernel = NexusKernel()
    text = "Not a json at all."
    data = kernel.extract_json(text)
    assert data == {}
