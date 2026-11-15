# Walkthroughs

End-to-end code tours. Each one follows one user action through the real code, with diagrams and links to the exact lines. Start with the chat message: it touches every layer.

| Walkthrough | Follows |
|---|---|
| [One chat message](chat-message.md) | browser to FastAPI to LangGraph to the LLM and back, as streamed events |
| [Voice pipeline](voice-pipeline.md) | microphone to speech-to-text, and reply text to streamed speech |
| [Security model](security-model.md) | the layers a request passes: cookies, CSRF, CSP, rate limits, encryption |
| [Lessons and spaced review](lessons-and-review.md) | a lesson's phases, and how due words come back with SM-2 |
| [LLM evals](llm-evals.md) | `make eval`, from a YAML case to a score, and the bug it caught |

Code links point at `main`. Line numbers were checked when each page was written, and can drift as the code changes.
