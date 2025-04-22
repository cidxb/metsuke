# Metsuke ✨

![Metsuke Logo](metsuke_logo.jpg)

**Metsuke (目つけ): AI-Assisted Development Task Manager**

The name "Metsuke" comes from Japanese, often translated as "gaze" or "looking". However, in disciplines like martial arts (Budo), it signifies much more than just physical sight. Metsuke refers to the *correct way of seeing* – encompassing not just *what* you look at, but *how* you perceive the whole situation, maintain focus, anticipate movement, and understand intent without being fixated on minor details. It implies focused awareness and comprehensive perception.

This project aims to bring that spirit of focused awareness and clear perception to the collaboration between human developers and AI assistants. By providing a structured plan and context (`PROJECT_PLAN.yaml`), Metsuke helps both human and AI maintain focus on the overall goals and current tasks, improving understanding and leading to more intentional, effective development.

## Why Metsuke? Enhancing Human-AI Collaboration 🤝

Working effectively with AI coding assistants requires clear communication and shared context. Metsuke is designed to work synergistically with AI coding assistants. Its structured approach using `PROJECT_PLAN.yaml` is particularly effective when the AI assistant also operates under a structured protocol (like RIPER-5) that emphasizes clear planning, execution, and review phases. This combination helps ensure predictable, reliable, and aligned collaboration. Metsuke bridges the gap by providing a structured framework based on a `PROJECT_PLAN.yaml` file, leading to significant benefits for both the human developer and the AI:

**For the Human Developer:** 🧑‍💻

*   **Clarity & Overview:** Get a clear, persistent view of project goals, context, and task status, reducing mental overhead.
*   **Structured Planning:** Define tasks, dependencies, and priorities explicitly.
*   **Improved AI Guidance:** Formulate requests to the AI with less ambiguity by referencing specific tasks and context from the plan.
*   **Reliable Context:** Avoid losing critical context buried in long chat histories.
*   **Easier Verification:** Quickly check if AI actions align with the planned tasks.
*   **Interactive TUI Dashboard (`metsuke tui`):** Gain real-time visibility into the project's status through an optional terminal interface. Visually track task completion progress, view status/priority breakdowns, explore dependencies, check suggested next steps, and monitor internal logs—all providing a convenient, high-level overview of the ongoing work and the AI's activity.

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
# Core CLI/Library (includes TUI)
pip install metsuke

# For development:
pip install -e .
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

## Terminal User Interface (TUI)  TUI

The Metsuke TUI provides a visual and interactive way to explore the `PROJECT_PLAN.yaml` content (or multiple plan files in a `plans/` directory) directly in your terminal. It automatically monitors the plan file(s) for changes and updates the display in real-time.

<p align="center">
  <img src="metsuke_screenshot.png" alt="Metsuke TUI Screenshot"/>
</p>

**Launching the TUI:**

To launch the TUI, simply run the command:
```bash
metsuke tui
```

**Interface Overview:**

*   **Top Area:** Displays the project title (`Metsuke`) and project metadata (Version, Name, License) loaded from the plan.
*   **Dashboard:** A panel showing high-level statistics:
    *   *Left Panel:* Overall task progress bar, counts of tasks by status (Done, In Progress, Pending, Blocked), and a breakdown of tasks by priority (High, Medium, Low).
    *   *Right Panel:* Dependency metrics (e.g., number of ready tasks, blocked tasks) and a suggestion for the next task to work on based on priority and readiness.
*   **Task Table:** A scrollable table listing all tasks with their ID, Title, Status, Priority, and Dependencies.
*   **Log View (Hidden by default):** A panel at the bottom (toggle with `Ctrl+D`) that shows internal TUI logging messages, useful for debugging.
*   **Status Bar:** Docked at the very bottom, showing the current time and author information.
*   **Footer:** Displays the primary key bindings for quick reference.

**Key Features & Bindings:**

*   **Navigation:** Use the `Up`/`Down` arrow keys to navigate through the Task Table.
*   **Help / Context (`?`):** Press `?` to open a modal screen. This screen displays:
    *   The full project `context` defined in `PROJECT_PLAN.yaml`.
    *   A detailed list of all available key bindings.
    *   Press `Esc` or `Q` to close the Help screen.
*   **Log Panel:**
    *   `Ctrl+D`: Toggles the visibility of the Log View panel at the bottom.
    *   `Ctrl+L`: Copies the entire content of the Log View to your system clipboard (requires `pyperclip` to be functional).
*   **Command Palette (`Ctrl+P`):** Opens Textual's built-in command palette, allowing access to actions like changing the color theme, toggling dark/light mode, etc.
*   **Quit (`Q`):** Press `Q` to exit the TUI application.

**File Monitoring:**

The TUI automatically watches the `PROJECT_PLAN.yaml` file. If you modify and save the file while the TUI is running, it will detect the change, reload the data, and refresh the display with the updated information.

## Tutorial: Getting Started & AI Collaboration Workflow 🚀

This tutorial guides you through the entire process of setting up Metsuke for a new project and using it to collaborate effectively with an AI coding assistant.

**1. Get the Code**

First, clone the Metsuke repository (or your project's repository if Metsuke is added as a dependency later):
```bash
# Replace with the actual repository URL if different
git clone https://github.com/your_username/metsuke.git 
cd metsuke
```

**2. Setup Environment & Install**

It's highly recommended to use a Python virtual environment.
(Requires Anaconda or Miniconda installed)
```bash
# python -m venv .venv # Old venv command
# source .venv/bin/activate # On Windows use `.venv\Scripts\activate` # Old venv command
conda create --name metsuke-env python=3.9 -y # Or choose another Python version >= 3.8
conda activate metsuke-env
```
Install Metsuke in editable mode (includes TUI dependencies):
```bash
pip install -e .
```

**3. Initialize the Plan**

Navigate to your project's root directory (if you cloned Metsuke, you are already there) and run:
```bash
metsuke init
```
This command:
*   Checks if a `PROJECT_PLAN.yaml` already exists (and exits if it does).
*   Attempts to detect your project's name and version from `pyproject.toml` (but uses placeholders in the generated file).
*   Creates a `PROJECT_PLAN.yaml` file containing:
    *   Collaboration guidelines (comments at the top).
    *   Placeholder project metadata (`name: Your Project Name`, `version: '0.1.0'`).
    *   A default project context section (you should edit this!).
    *   A list of common starting tasks (you should customize these!).

**Important:** Open the newly created `PROJECT_PLAN.yaml` and customize the `project`, `context`, and initial `tasks` to match your actual project requirements.

**4. Open in AI-Powered Editor**

Open your project folder in an AI-powered code editor that supports direct interaction with an AI assistant, such as Cursor or VS Code with appropriate extensions.

**5. Engage the AI Assistant**

This is a crucial step for enabling effective collaboration.
You need to **explicitly instruct your AI assistant to use the `PROJECT_PLAN.yaml` file** as the foundation for your work together.

Example prompts:

> *   "Please read the `PROJECT_PLAN.yaml` file to understand the project goals, context, and current tasks."*
> *   "Let's use `PROJECT_PLAN.yaml` as our single source of truth for planning and tasks."
> *   "Refer to the tasks and context in `PROJECT_PLAN.yaml` for our development work going forward."
> *   "I have a `PROJECT_PLAN.yaml` file defining our project. Please make sure you load and reference it."

Ensure the AI acknowledges that it has access to and will use the file. Some advanced AI integrations might detect and use the file automatically, but explicit instruction is the most reliable approach.

**6. Collaborative Workflow Example**

Here's how a typical interaction might look, assuming the AI assistant understands Metsuke and ideally follows a structured protocol (like RIPER-5):

> **You:** "We need a new feature to detect circular dependencies in the plan file itself. Please add this as a new task to `PROJECT_PLAN.yaml`, priority 'medium'."
>
> **AI Assistant (using Metsuke):** (Reads `PROJECT_PLAN.yaml`, finds last ID was 5) "Okay, I will add **Task 6: Implement dependency cycle detection**, priority 'medium', depending on Task 2 (Define core data models). Does this plan look good for the description: '**Plan:** 1. Represent task dependencies as a graph. 2. Implement a graph traversal algorithm (e.g., Depth First Search). 3. Detect back edges during traversal which indicate cycles. 4. Report cycles found.'?"
>
> **You:** "Yes, that plan looks good. Please add it."
>
> **AI Assistant:** (Uses file editing tool) "Okay, I have added Task 6 to `PROJECT_PLAN.yaml`."
>
> **You:** "Now, please implement Task 6."
>
> **AI Assistant:** "Acknowledged. Entering EXECUTE mode for **Task 6: Implement dependency cycle detection**. Based on the plan, I will first represent dependencies as a graph..." *(Proceeds with implementation, potentially involving further planning/review steps based on its protocol)*
>
> *(...Implementation happens...)*
>
> **AI Assistant:** "Implementation for Task 6 is complete. **Test Method:** Create a test plan file `PROJECT_PLAN_cycle.yaml` with a known dependency cycle (e.g., Task A depends on B, Task B depends on A). Call the new function `core.detect_cycles('PROJECT_PLAN_cycle.yaml')` and assert that it returns `True`."
>
> **You:** *(You run the test)* "Confirmed, the test passes."
>
> **You:** "Please mark Task 6 as Done in the plan file."
>
> **AI Assistant:** (Uses file editing tool) "Understood. Updating status for Task 6 to 'Done' in `PROJECT_PLAN.yaml`."

**Outcome:**

This workflow, facilitated by Metsuke and a cooperating AI, ensures:
*   **Clarity:** Both user and AI reference the same plan.
*   **Traceability:** Changes (like adding Task 6) are reflected in the plan.
*   **Structure:** Development follows defined tasks and dependencies.
*   **Verification:** The AI proposes a test method, and the user confirms completion.

This structured approach minimizes misunderstandings and keeps the development process focused and efficient.

## Development 🛠️

See `PROJECT_PLAN.yaml` for the development roadmap and task breakdown.

## License 📄

This project is licensed under the Apache License 2.0. See the `LICENSE` file for details.
