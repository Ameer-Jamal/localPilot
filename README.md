# LocalPilot

Local, private AI chat for JetBrains IDEs, backed by Ollama.

**LocalPilot** lets you highlight code in IntelliJ, PyCharm, WebStorm, or Android Studio and open a dedicated chat that stays pinned to that exact selection. It is designed for people who want fast local assistance without sending source code to a cloud model.

<img width="1115" height="1192" alt="LocalPilot chat window" src="https://github.com/user-attachments/assets/fed472d3-b267-492a-9838-bb30c83b3aae" />

## Why LocalPilot

- Fully local. Uses your Ollama server on `localhost`.
- Private by default. Your code stays on your machine.
- Selection-aware. Each highlighted snippet opens in its own chat context.
- Built for iteration. Tabs, saved chats, quick prompts, streaming, and code-copy buttons are all in the desktop app.
- Practical controls. You can start Ollama, stop what LocalPilot started, or release loaded models to free memory.

## Current features

- Tabbed chats per code selection
- Persistent chat history in local SQLite
- Left-side history panel with reopen and delete
- In-app settings for Ollama defaults, history retention, and quick prompts
- Editable quick prompt buttons
- Streaming responses with syntax highlighting
- Copy buttons on code blocks
- Concise AI-generated chat titles
- Always-on-top toggle
- Stop generation anytime
- Browser-style `+` tab for blank chats

## Requirements

- macOS
- Python 3.10+
- Ollama installed locally
- At least one Ollama model pulled, such as `qwen2.5-coder:7b`, `gemma3:12b`, `llama3.1`, or `mistral`

LocalPilot can work with Ollama already running, or it can try to start Ollama from the app when needed.

## Quick start

```bash
git clone https://github.com/Ameer-Jamal/localPilot.git
cd localPilot
python3 installer.py
```

This will:

- create the launcher at `~/.local/bin/localpilot`
- register a user-level JetBrains External Tool named `LocalPilot`
- support both legacy and newer JetBrains external-tool XML layouts

After install, fully quit your IDE and relaunch it so JetBrains reloads the external tool configuration.

## Using it

1. Highlight code in your IDE.
2. Run `Tools -> External Tools -> LocalPilot`.
3. Ask a question in the LocalPilot window.

What you get in the app:

- the selected code is pinned at the top of the chat
- each new selection opens in its own tab
- `Settings` lets you manage runtime defaults, quick prompts, and history retention
- `History` shows saved chats you can reopen later
- `Stop` cancels the current response
- `Stop Ollama` stops the Ollama process if LocalPilot launched it, or releases loaded models if it did not

You can also open a blank tab with the `+` tab and use LocalPilot as a general local coding chat, not just for pinned selections.

## Settings and persistence

Most configuration is now done in the app, not by editing Python files.

Runtime settings in the UI include:

- Ollama API base URL
- default model to install
- temperature
- context window
- keep-alive duration
- local Ollama launch defaults

Quick prompts in the UI can be:

- added
- edited
- removed
- reset to the starter set

History settings in the UI include:

- keep history forever
- delete closed chats older than `N` days
- cap total stored sessions
- clear all saved history manually

Saved history lives at:

```text
~/.localpilot/history.db
```

You can override storage paths with:

- `LOCALPILOT_HOME`
- `LOCALPILOT_HISTORY_DB`

For advanced environment overrides:

- `OLLAMA_URL` changes the Ollama API base URL
- `MODEL_LIST` pins the visible model list

## Ollama notes

If you prefer to run Ollama yourself, a typical local setup looks like:

```bash
OLLAMA_NUM_PARALLEL=2 \
OLLAMA_MAX_LOADED_MODELS=1 \
OLLAMA_FLASH_ATTENTION=1 \
OLLAMA_KV_CACHE_TYPE=q8_0 \
ollama serve
```

LocalPilot also has a settings UI for these launch defaults, so most users do not need to keep editing shell commands manually.

## Troubleshooting

Run:

```bash
python3 installer.py doctor
```

This prints which IDE configs contain the `LocalPilot` tool and whether the launcher exists.

Common fixes:

- **I do not see the tool in the IDE.**  
  Run `python3 installer.py` again, then fully quit and relaunch the IDE.

- **The tool exists but nothing happens when I run it.**  
  In JetBrains External Tools, verify:

  - Program: `~/.local/bin/localpilot`
  - Parameters:

    ```text
    --file $FileName$ --filepath $FilePath$ \
    --sel-start $SelectionStart$ --sel-end $SelectionEnd$ \
    --sel-start-line $SelectionStartLine$ --sel-start-col $SelectionStartColumn$ \
    --sel-end-line $SelectionEndLine$ --sel-end-col $SelectionEndColumn$
    ```

  You can also test the launcher directly:

  ```bash
  ~/.local/bin/localpilot --selection "hello" --file demo.txt
  ```

- **A project-level tool is shadowing the user-level tool.**

  ```bash
  python3 installer.py uninstall --purge-project
  python3 installer.py install
  ```

- **Android Studio shows the tool but nothing opens.**  
  Fully restart Android Studio, then run `python3 installer.py doctor`.

- **Large selections behave oddly.**  
  LocalPilot accepts both offset-based and line/column-based selection macros from JetBrains. If your IDE passes raw macro text instead of expanded values, LocalPilot falls back to reading from the file or stdin.

## Uninstall

```bash
python3 installer.py uninstall
python3 installer.py uninstall --purge-project
```

## Privacy

All inference is local. LocalPilot only talks to your local Ollama server.

## Contributing

PRs are welcome. If you contribute:

- keep the installer idempotent
- avoid destructive changes to existing JetBrains tool configs
- avoid breaking `~/.local/bin/localpilot`
- test at least one IntelliJ build and one PyCharm build if you touch installer behavior

## License

Copyright © 2025 Ameer Jamal  
Licensed under the [Custom Non-Commercial License](LICENSE).

Personal and academic use are allowed. Commercial use, redistribution, or integration into proprietary products requires prior written permission.
