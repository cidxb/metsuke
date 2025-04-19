# Metsuke ✨

**Metsuke (目つけ): AI-Assisted Development Task Manager**

The name "Metsuke" comes from Japanese, often translated as "gaze" or "looking". However, in disciplines like martial arts (Budo), it signifies much more than just physical sight. Metsuke refers to the *correct way of seeing* – encompassing not just *what* you look at, but *how* you perceive the whole situation, maintain focus, anticipate movement, and understand intent without being fixated on minor details. It implies focused awareness and comprehensive perception.

This project aims to bring that spirit of focused awareness and clear perception to the collaboration between human developers and AI assistants. By providing a structured plan and context (`PROJECT_PLAN.yaml`), Metsuke helps both human and AI maintain focus on the overall goals and current tasks, improving understanding and leading to more intentional, effective development.

## Why Metsuke? Enhancing Human-AI Collaboration 🤝

Working effectively with AI coding assistants requires clear communication and shared context. Metsuke bridges the gap by providing a structured framework based on a `PROJECT_PLAN.yaml` file, leading to significant benefits for both the human developer and the AI:

**For the Human Developer:** 🧑‍💻

*   **Clarity & Overview:** Get a clear, persistent view of project goals, context, and task status, reducing mental overhead.
*   **Structured Planning:** Define tasks, dependencies, and priorities explicitly.
*   **Improved AI Guidance:** Formulate requests to the AI with less ambiguity by referencing specific tasks and context from the plan.
*   **Reliable Context:** Avoid losing critical context buried in long chat histories.
*   **Easier Verification:** Quickly check if AI actions align with the planned tasks.

**For the AI Assistant:** 🤖

*   **Structured Input:** Receive project state, context, and task details in a predictable, machine-readable format.
*   **Focused Tasks:** Understand the specific goal of each request within the larger project plan.
*   **Relevant Context:** Access necessary background information directly from the plan file.
*   **Improved Accuracy:** Generate more relevant code and suggestions based on clear context and task definitions.
*   **Reduced Deviation:** Minimize guesswork and actions outside the scope of the agreed-upon plan.

**Synergy & Performance:** 👍

*   **Shared Understanding:** Creates a single source of truth for the project plan, minimizing miscommunication.
*   **Predictable Collaboration:** Makes the AI's behavior more aligned with the developer's intent.
*   **Faster Progress:** Reduces time spent on clarifying instructions or correcting off-track AI work.
*   **Higher Quality:** Promotes better outcomes through structured planning and focused execution.

By using Metsuke, the human-AI development team can collaborate more effectively, leading to faster, more robust, and more predictable results.

### Example: Metsuke in Action ▶️

Imagine the following exchange without Metsuke:

> **User:** Can you update the status bar to show the date?
> **AI:** Sure, I'll modify the `StatusBar` widget... *(Proceeds to edit code that might not exist yet or is in the wrong place)*

Now, contrast that with a Metsuke-guided interaction:

> **User:** Please work on **Task 16** (Enhance TUI StatusBar Display).
>
> **AI Assistant (using Metsuke):** Okay, I see Task 16 is to enhance the `StatusBar` display with the date. Let me check the plan...
> ```yaml
> - id: 16
>   title: Enhance TUI StatusBar Display
>   # ...
>   status: pending
>   dependencies: [ 9 ]
> - id: 9
>   title: Structure TUI Code within Package
>   # ...
>   status: pending
> ```
> **AI Assistant:** Task 16 depends on **Task 9** (`Structure TUI Code within Package`), which is still `pending`. We need to complete Task 9 first by refactoring the TUI code into `src/metsuke/tui/` before I can safely modify the `StatusBar`. Shall we proceed with Task 9 instead?

This example demonstrates how Metsuke provides:

*   **Unambiguous Task Reference:** The user clearly specifies Task 16.
*   **Dependency Awareness:** The AI checks `PROJECT_PLAN.yaml` and correctly identifies the prerequisite (Task 9).
*   **Error Prevention:** The AI avoids potentially harmful actions by respecting the planned dependencies.
*   **Guided Workflow:** The collaboration stays focused and follows the logical development order.

## Features (Planned) 💡

*   **YAML-based Planning:** Define project context, goals, and tasks in a human-readable and machine-parseable format.
*   **CLI Interface:** View project info, list tasks, check status (including TUI via `metsuke tui`).
*   **Library API:** Programmatically load, validate, and potentially modify project plans.
*   **Task Management:** Track task status (pending, in_progress, done, etc.) and dependencies.
*   **Context Awareness:** Provides a central place for project context, easily accessible by both humans and AI.

## Installation 📦

```bash
# Core CLI/Library
pip install metsuke

# For the Terminal UI (TUI)
pip install metsuke[tui]

# For development:
pip install -e .
# For TUI development:
pip install -e '.[tui]'
```

## Usage ⌨️

**Command Line Interface (CLI):**

```bash
# View project info
metsuke show-info

# List tasks
metsuke list-tasks

# Launch Terminal UI (Requires TUI dependencies)
metsuke tui

# (More commands to come)
```

**Library Usage:**

```python
from metsuke import load_plan, PlanLoadingError, PlanValidationError

try:
    project_plan = load_plan("PROJECT_PLAN.yaml")
    print(f"Project Name: {project_plan.project.name}")
    for task in project_plan.tasks:
        print(f"- Task {task.id}: {task.title} ({task.status})")
except (PlanLoadingError, PlanValidationError) as e:
    print(f"Error loading plan: {e}")
```

## Development 🛠️

See `PROJECT_PLAN.yaml` for the development roadmap and task breakdown.

## License 📄

This project is licensed under the Apache License 2.0. See the `LICENSE` file for details.
