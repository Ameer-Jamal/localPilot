"""Small utilities and static prompts."""

ACTIONS = {
    "explain": "Explain what this code does, list concrete risks, and propose improvements.",
    "refactor": "Refactor for readability and micro-performance. Return a unified diff only. Preserve behavior.",
    "tests": "Generate focused unit tests with Arrange-Act-Assert and edge cases.",
}


def lang_hint(filename: str) -> str:
    """Best-effort language hint from a file name."""
    fn = (filename or "").lower()
    mapping = {
        ".py": "python", ".java": "java", ".kt": "kotlin", ".ts": "typescript", ".tsx": "tsx",
        ".js": "javascript", ".jsx": "jsx", ".go": "go", ".rb": "ruby", ".cs": "csharp",
        ".c": "c", ".h": "c", ".cpp": "cpp", ".cc": "cpp", ".hpp": "cpp", ".m": "objectivec", ".mm": "objectivec",
        ".scss": "scss", ".css": "css", ".html": "html", ".sql": "sql", ".xml": "xml",
        ".yml": "yaml", ".yaml": "yaml", ".sh": "bash", ".json": "json",
    }
    for ext, lang in mapping.items():
        if fn.endswith(ext):
            return lang
    return "plaintext"


def build_prompt(task: str, code: str, lang: str) -> str:
    return (
        "You are a senior software engineer. Be concise and precise.\n\n"
        f"Task:\n{task}\n\n"
        f"Code:\n```{lang}\n{code}\n```"
    )
