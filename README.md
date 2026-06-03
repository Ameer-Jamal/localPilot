# LocalPilot

Local, private AI chat for JetBrains IDEs, backed by Ollama.

**LocalPilot** lets you highlight code in IntelliJ, PyCharm, WebStorm, or Android Studio and open a dedicated chat that stays pinned to that exact selection. It is designed for people who want fast local assistance without sending source code to a cloud model.

<img width="1115" height="1192" alt="LocalPilot chat window" src="https://github.com/user-attachments/assets/fed472d3-b267-492a-9838-bb30c83b3aae" />
<img width="1442" height="850" alt="image" src="https://github.com/user-attachments/assets/9faa1ffe-389e-4bae-9d23-8aff87968146" />
<img width="929" height="750" alt="image" src="https://github.com/user-attachments/assets/63a9640b-f441-4816-9aca-27deeab10d88" />
<img width="2557" height="1404" alt="image" src="https://github.com/user-attachments/assets/272856b2-f560-4fb5-a18f-ec306b8ea01f" />
<img width="968" height="888" alt="image" src="https://github.com/user-attachments/assets/34d0e323-f6b8-4b10-aaf5-610ae69b69d3" />
<img width="975" height="889" alt="image" src="https://github.com/user-attachments/assets/af832134-a834-437c-9b1f-91f111d839d2" />

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
- optional AWS Bedrock profile, region, and model selection

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

## AWS Bedrock

LocalPilot can also use AWS Bedrock models in the same model dropdown as Ollama. Bedrock is optional and disabled by default.

Requirements:

- `boto3` installed from `requirements.txt`
- AWS CLI installed
- an AWS profile with Bedrock access
- if your profile uses AWS SSO, a valid SSO login session

Typical AWS setup:

```bash
export AWS_PROFILE="your-profile"
export AWS_REGION="us-east-1"
aws sso login --profile "$AWS_PROFILE"
```

How to enable it in LocalPilot:

1. Open `Settings`.
2. In the `AWS Bedrock` section, enable Bedrock.
3. Choose an AWS profile.
4. Choose an AWS region.
5. Click `AWS SSO Login` if the selected profile uses SSO.
6. Click `Refresh Bedrock Models`.

Model selection notes:

- LocalPilot now filters the Bedrock list to active, chat-capable inference profiles.
- Prefer current inference-profile IDs such as `global.anthropic.claude-sonnet-4-6`, `us.amazon.nova-pro-v1:0`, or the `us.meta.llama4-*` profiles.
- Old or legacy raw foundation-model IDs may appear in AWS generally, but LocalPilot should avoid offering the ones that are known to fail with `Converse`.
- Bedrock models are tinted differently in the main model dropdown so they are easy to distinguish from Ollama models.

Common Bedrock issues:

- **`ForbiddenException` / `GetRoleCredentials`**  
  Your AWS profile is not logged in or does not have Bedrock access. Run:

  ```bash
  aws sso login --profile "$AWS_PROFILE"
  ```

- **`ValidationException` saying an inference profile is required**  
  That model needs an inference profile ID instead of a raw foundation-model ID. Refresh the Bedrock list and pick one of the Bedrock entries offered by LocalPilot.

- **`ResourceNotFoundException` for legacy or end-of-life models**  
  The selected model is no longer usable for your account or region. Refresh the Bedrock list and choose a newer profile.

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
