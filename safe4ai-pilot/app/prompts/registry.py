from app.prompts.templates import TEMPLATES, PromptTemplate


def get_prompt(name: str, version: str = "latest") -> PromptTemplate:
    matches = [t for t in TEMPLATES if t.name == name]
    if not matches:
        raise KeyError(f"No prompt template found with name={name!r}")
    if version == "latest":
        return matches[-1]
    for t in matches:
        if t.version == version:
            return t
    raise KeyError(f"Prompt {name!r} version {version!r} not found")
