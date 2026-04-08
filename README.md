# LocalPilot — local, free, private AI for your JetBrains IDE

**LocalPilot** lets you highlight code in IntelliJ, PyCharm, WebStorm, or Android Studio and instantly chat with a fully
local LLM about that exact selection.
<img width="1115" height="1192" alt="image" src="https://github.com/user-attachments/assets/fed472d3-b267-492a-9838-bb30c83b3aae" />
<img width="936" height="1319" alt="image" src="https://github.com/user-attachments/assets/384df695-9fc0-42ad-8538-4975ed249742" />
<img width="953" height="706" alt="image" src="https://github.com/user-attachments/assets/b21a2c98-a745-450b-a8bc-ab37a4b2fa7c" />
 
- 🧠 **Local & free**: uses your **Ollama** on `localhost` (no cloud, no tokens)
- 🔒 **Private by design**: your code never leaves your machine
- 🧵 **Tabbed chats** per selection
- 💾 **Persistent history** stored locally in SQLite
- ⚙️ **Settings UI** for Ollama defaults and quick prompts
- 📌 **Always-on-top** toggle (persists)
- ⏱️ **Streaming** responses with free scrolling
- 📋 **Copy code** buttons on blocks
- ⛔ **Stop** generating anytime

---

## Requirements

* **macOS** (tested on Apple Silicon).
* **Python 3.10+**
* **Ollama** installed and serving locally. Example (adjust to your machine):

```bash  
  OLLAMA_NUM_PARALLEL=2 \
  OLLAMA_MAX_LOADED_MODELS=1 \
  OLLAMA_FLASH_ATTENTION=1 \
  OLLAMA_KV_CACHE_TYPE=q8_0 \
  ollama serve
```

* A model pulled in Ollama (e.g. `llama3.1`, `qwen2.5-coder`, `mistral`).
  Local Pilot will try and configure the URL and get all the models installed on your machine

---

## Quick start (90 seconds)

```bash
git clone https://github.com/Ameer-Jamal/localPilot.git
cd localPilot
python3 installer.py
```

What this does:

* Writes a launcher at `~/.local/bin/localpilot`.
* Registers a user-level **External Tool: “LocalPilot”** in all detected JetBrains/Android Studio configs (supports both
  legacy and modern XML schemas).

> **Important:** Fully **quit** the IDE(s) (Cmd+Q), then relaunch so they reload the updated config.

---

## Using it in the IDE

1. Highlight any code in the editor.
2. Run **Tools → External Tools → LocalPilot** (or bind a keyboard shortcut or use global search by pressing shift twice and searching for "LocalPilot").
3. A small chat window opens:

    * The pinned **code context** is at the top (collapsible).
    * Type your question (Cmd/Ctrl+Enter to send).
    * Or use the built in quick commands
    * Use **Settings** to change Ollama defaults and add/edit/remove quick prompt buttons
    * Use **Stop** to cancel generation.
    * **Copy** appears on code blocks (always visible; shows “Copied!” on click).
    * **Pin** (top-left) keeps the window floating above your IDE; state persists.

Each new code selection opens a **new tab** so conversations don’t mix. Closing the last tab closes the window (with a
“Are you sure?” safety prompt if something is still generating). Open tabs are restored on the next launch, and their
history is saved locally in `~/.localpilot/history.db`.

---

## Configuration

Runtime settings live in `config.py`:

```python
OLLAMA_BASE_URL = "http://localhost:11434/api"
TEMP = 0.2
NUM_CTX = 16384
KEEP_ALIVE = "10m"
DEFAULT_PULL_MODEL = "qwen2.5-coder:7b"
```

UI tweaks you may like:

* Default always-on-top: toggle via the pin button; persists in `QSettings` as `ui/pin_on_top`.
* HTML theme / syntax highlight: see `resources/html_template.py` & `resources/template.html`.
* Behavior (tabs, copy styling, autoscroll): in `ui/session_widget.py`.

Environment overrides:

* `OLLAMA_URL` to point at a different Ollama API base URL
* `MODEL_LIST` to pin the visible model list
* `LOCALPILOT_HOME` or `LOCALPILOT_HISTORY_DB` to move persistent history

Most day-to-day changes no longer require editing code directly; use the in-app **Settings** button to manage Ollama
runtime defaults and quick prompt buttons.

---

## Uninstall

```bash
python3 installer.py uninstall
# optionally remove any project-level tool that could shadow user-level config
python3 installer.py uninstall --purge-project
```

---

## Doctor (troubleshooting)

```bash
python3 installer.py doctor
```

This prints which IDE configs contain the **LocalPilot** tool and whether the launcher exists.

Common fixes:

* **I don’t see the tool in the IDE.**
  Run `python3 installer.py` again, then **fully quit and relaunch** the IDE.
  Some IDEs read from `~/Library/Application Support/<IDE>/options/tools.xml`, others from `…/tools/External Tools.xml`.
  The installer writes **both**.

* **Tool exists but nothing happens when I run it.**
  In Preferences → Tools → External Tools → **LocalPilot**, verify:

    * **Program:** `~/.local/bin/localpilot`
    * **Parameters:**

      ```
      --file $FileName$ --filepath $FilePath$ \
      --sel-start $SelectionStart$ --sel-end $SelectionEnd$ \
      --sel-start-line $SelectionStartLine$ --sel-start-col $SelectionStartColumn$ \
      --sel-end-line $SelectionEndLine$ --sel-end-col $SelectionEndColumn$
      ```

      Also try the launcher directly:

      ```bash
      ~/.local/bin/localpilot --selection "hello" --file demo.txt
      ```

* **A project-level tool is shadowing LocalPilot.**
  Run:

  ```bash
  python3 installer.py uninstall --purge-project
  python3 installer.py install
  ```

* **Android Studio shows the menu but nothing opens.**
  Ensure Android Studio is **quit/restarted** after install. Then run `python3 installer.py doctor` to confirm the tool
  entry is **FOUND** for Android Studio’s config root.

* **Large selections / “first character missing.”**
  The script accepts offsets and 1-based line/column macros from JetBrains. If IntelliJ still passes raw `$Selection…$`
  text (unexpanded), LocalPilot falls back to reading the selection from the file or stdin. If you still see trimming,
  please open an issue with the exact command printed in *Run* → *External Tools* console.

---

## Privacy

All inference is local. Your code never leaves your machine. LocalPilot only talks to your local Ollama server.

---

## Contributing

PRs welcome! Please:

* Keep installer idempotent and non-destructive of other tools.
* Test against at least one IntelliJ & one PyCharm version.
* Avoid breaking `~/.local/bin/localpilot`.

---

## License

Copyright © 2025 Ameer Jamal <br>
This project is licensed under the [Custom Non-Commercial License](LICENSE) <br>
This project is open for personal or academic use only.
Commercial use, redistribution, or integration into proprietary products is prohibited without prior written permission.
