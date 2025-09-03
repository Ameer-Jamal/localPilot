# LocalPilot — local, free, private AI for your JetBrains IDE

**LocalPilot** lets you highlight code in IntelliJ, PyCharm, WebStorm, or Android Studio and instantly chat with a fully
local LLM about that exact selection.

- 🧠 **Local & free**: uses your **Ollama** on `localhost` (no cloud, no tokens)
- 🔒 **Private by design**: your code never leaves your machine
- 🧵 **Tabbed chats** per selection
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
  Configure model/URL in `ollama_client.py`.

### Running multiple models

LocalPilot lists models that are currently **running**. If none are active you'll see “No Ollama models running” and chat is disabled.

1. Allow more than one model to stay loaded:

   ```bash
   OLLAMA_MAX_LOADED_MODELS=2 ollama serve
   ```

2. Start (or "warm up") each model you plan to use:

   ```bash
   ollama run llama3 &
   ollama run qwen2.5-coder &
   ```

3. Inspect which models are running:

   ```bash
   ollama ps
   # or
   curl http://localhost:11434/api/ps
   ```

   LocalPilot queries the same `/ps` endpoint for the model selector.

You can also override the selector with a comma-separated `MODEL_LIST` environment variable if you prefer a static list.
During chat the terminal running LocalPilot prints the requested model and the model reported by Ollama so you can verify which one handled the response.

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
2. Run **Tools → External Tools → LocalPilot** (or bind a keyboard shortcut).
3. A small chat window opens:

    * The pinned **code context** is at the top (collapsible).
    * Type your question (Cmd/Ctrl+Enter to send).
    * Use **Stop** to cancel generation.
    * **Copy** appears on code blocks (always visible; shows “Copied!” on click).
    * **Pin** (top-left) keeps the window floating above your IDE; state persists.

Each new code selection opens a **new tab** so conversations don’t mix. Closing the last tab closes the window (with a
“Are you sure?” safety prompt if something is still generating).

---

## Configuration

Open `ollama_client.py`:

```python
MODEL = "llama3.1"  # set your favorite local model here
TEMP = 0.2  # sampling temperature
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"  # change if you proxy/remote
```

UI tweaks you may like:

* Default always-on-top: toggle via the pin button; persists in `QSettings` as `ui/pin_on_top`.
* HTML theme / syntax highlight: see `resources/html_template.py` & `resources/template.html`.
* Behavior (tabs, copy styling, autoscroll): in `ui/session_widget.py`.

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

All inference is local. Your code never leaves your machine—LocalPilot only talks to your local Ollama server.

---

## Contributing

PRs welcome! Please:

* Keep installer idempotent and non-destructive of other tools.
* Test against at least one IntelliJ & one PyCharm version.
* Avoid breaking `~/.local/bin/localpilot`.

---

## License

MIT © Ameer Jamal
