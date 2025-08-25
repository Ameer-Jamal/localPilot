ACTIONS = {
    "explain": "Explain what this code does, list concrete risks, and propose improvements.",
    "refactor": "Refactor for readability and micro-performance. Return a unified diff only. Preserve behavior.",
    "tests": "Generate focused unit tests with Arrange-Act-Assert and edge cases.",
}

def lang_hint(filename: str) -> str:
    fn = (filename or "").lower()
    for ext, lang in {
        ".java":"java", ".kt":"kotlin", ".ts":"typescript", ".tsx":"tsx",
        ".js":"javascript", ".jsx":"jsx", ".py":"python", ".go":"go",
        ".rb":"ruby", ".cs":"csharp", ".c":"c", ".cpp":"cpp", ".h":"c",
        ".scss":"scss", ".css":"css", ".html":"html", ".sql":"sql",
        ".xml":"xml", ".yml":"yaml", ".yaml":"yaml", ".sh":"bash",
    }.items():
        if fn.endswith(ext): return lang
    return ""

def build_prompt(task: str, code: str, lang: str) -> str:
    return (
        "You are a senior software engineer. Be concise and precise.\n\n"
        f"Task:\n{task}\n\n"
        f"Code:\n```{lang}\n{code}\n```"
    )
