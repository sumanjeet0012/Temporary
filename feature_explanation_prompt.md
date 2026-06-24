You are an experienced senior engineer helping me understand a feature that has evolved through multiple AI-assisted changes.

I will provide you with the current codebase (or relevant files). Your job is to reconstruct a COMPLETE understanding of the feature as if you are writing internal technical documentation for a new developer joining the team.

Create a well-structured markdown document with the following sections:

## 1. Feature Overview
- What problem this feature solves
- Why this feature exists
- Real-world use cases

## 2. High-Level Flow
- Step-by-step explanation of how the feature works from start to finish
- Include user interaction → system behavior → output

## 3. Entry Points (Top-Level API)
- What functions, classes, or CLI commands are used to interact with this feature
- Example usage (code snippets if possible)

## 4. Architecture & Components
- Break down major modules/files involved
- Explain responsibilities of each component
- Show how components interact

## 5. Execution Flow (Under the Hood)
- Walk through the actual call chain
- Explain how data flows between functions/modules
- Mention key transformations or decisions

## 6. Important Concepts & Data Structures
- Key objects, schemas, or patterns used
- Why they are designed that way

## 7. External Dependencies
- Libraries, services, or APIs used
- What role they play

## 8. Side Effects & Edge Cases
- Anything non-obvious
- Error handling, retries, async behavior, etc.

## 9. Minimal Working Example
- Show a simple example that demonstrates how to use the feature

## 10. Mental Model (Very Important)
- Provide a simple analogy or mental model to understand this system easily

## 11. Things That Might Be Confusing
- Call out tricky parts or areas where AI-generated code might be misleading

Important:
- Do NOT just summarize code — explain the reasoning behind it
- Assume the reader wants deep understanding, not surface-level description
- Use diagrams (in text / ASCII if needed)
- Be explicit about flow and dependencies



After the doc, ask this to really lock in understanding:
Now walk through a real execution of this feature step-by-step.

Start from the entry point and simulate:
- Which function is called first
- What data is passed
- What happens next at each layer

Think like a debugger tracing execution.

Show the flow clearly with indentation or arrows.



Create a simple diagram of this feature's flow using ASCII or mermaid.
