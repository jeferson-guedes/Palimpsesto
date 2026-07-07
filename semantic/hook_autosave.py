#!/usr/bin/env python3
"""Hippocampal hook: extracts structured insights from conversation turns.

Zero external API cost. Strategy:
1. Clean noise (tool calls, system tags) but KEEP structured content (tables, lists, headers)
2. Extract bonus structure: facts, decisions, user corrections (pattern-based)
3. Always save substantial assistant responses (condensed) — the embedding carries semantics
4. Generate semantic tags from content analysis
5. Save structured result to ChromaDB
"""

import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

DATA_DIR = os.path.join(_SCRIPT_DIR, "data")
COLLECTION_NAME = "memory"
MAX_TRANSCRIPT_CHARS = 12000
MAX_SAVE_CHARS = 3000


def extract_text(content) -> str:
    """Extract plain text from a message content field."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return str(content)


def clean_text(text: str) -> str:
    """Remove tool noise and system tags but KEEP structured content."""
    # Remove XML-like tool/system blocks
    text = re.sub(r"<tool_use>.*?</tool_use>", "", text, flags=re.DOTALL)
    text = re.sub(r"<tool_result>.*?</tool_result>", "", text, flags=re.DOTALL)
    text = re.sub(r"<system-reminder>.*?</system-reminder>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[\w_]+>.*?</[\w_]+>", "", text, flags=re.DOTALL)
    text = re.sub(r"<local-command-.*?>.*?</local-command-.*?>", "", text, flags=re.DOTALL)
    # Remove large code blocks but keep small inline code
    text = re.sub(r"```[\w]*\n.{500,}?```", "[large code block]", text, flags=re.DOTALL)
    # Keep small code blocks (commands, short snippets) — they carry context
    # Remove file creation noise
    text = re.sub(r"(?:File created|updated) successfully at: .+", "", text)
    # Remove tool call metadata lines
    text = re.sub(r"^(?:Read|Edit|Write|Bash|Glob|Grep|Agent)\(.*\)$", "", text, flags=re.MULTILINE)
    # Collapse excessive whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def condense_text(text: str, max_chars: int) -> str:
    """Condense text to max_chars, preserving structure (headers, tables, lists)."""
    if len(text) <= max_chars:
        return text

    lines = text.split("\n")
    # Priority: headers > table rows > list items > other
    priority_lines = []
    other_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#") or stripped.startswith("|") or stripped.startswith("- ") or stripped.startswith("* "):
            priority_lines.append(line)
        elif re.match(r"^\d+\.", stripped):
            priority_lines.append(line)
        else:
            other_lines.append(line)

    # Build output: priority first, then fill with other lines
    result = []
    total = 0
    for line in priority_lines + other_lines:
        if total + len(line) + 1 > max_chars:
            break
        result.append(line)
        total += len(line) + 1

    return "\n".join(result)


def read_recent_turns(transcript_path: str) -> list[tuple[str, str]]:
    """Read recent conversation turns, return [(role, cleaned_text), ...]."""
    messages = []
    with open(transcript_path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    turns = []
    total_chars = 0
    for msg in reversed(messages):
        role = msg.get("type") or msg.get("role", "")
        if role not in ("assistant", "human", "user"):
            continue

        text = extract_text(
            msg.get("message", {}).get("content", "")
            if "message" in msg
            else msg.get("content", "")
        )
        text = clean_text(text)
        if not text or len(text) < 15:
            continue

        label = "user" if role in ("human", "user") else "assistant"
        if total_chars + len(text) > MAX_TRANSCRIPT_CHARS:
            break
        turns.append((label, text))
        total_chars += len(text)

    turns.reverse()
    return turns


# --- Extraction patterns ---

DECISION_PATTERNS = [
    r"(?:decidimos|decided|escolhemos|optamos|vamos usar|approach[:\s])",
    r"(?:melhor (?:abordagem|opcao|solucao)|tradeoff|trade-off)",
    r"(?:ao inves de|instead of|rather than|em vez de)",
    r"(?:solucao|solução|solution)[:\s]",
    r"(?:vou (?:implementar|criar|usar|fazer))",
    r"(?:proximo[s]? passo|next step|plano[:\s]|plan[:\s])",
    r"(?:status|estado atual|onde paramos|where we left)",
    r"(?:DONE|COMPLETO|CONCLU[IÍ]D[OA]|NAO INICIAD[OA]|PENDENTE|EM ANDAMENTO)",
    r"(?:fase \d|phase \d|etapa \d)",
]

CORRECTION_PATTERNS = [
    r"(?:nao faca|não faça|don'?t|nunca|never\b)",
    r"(?:pare de|stop doing|errado|wrong|incorreto)",
    r"(?:sempre use|always use|sempre faca|obrigat[oó]rio)",
    r"(?:prefiro|prefer[eo]|quero que)",
    r"(?:isso nao|não funciona|nao e assim|nao eh assim)",
]

FACT_PATTERNS = [
    r"(?:o (?:ip|host|port|url|endpoint|path) [eé])",
    r"(?:roda (?:em|no|na)|está (?:em|no|na)|fica (?:em|no|na))",
    r"(?:usa(?:mos)?|utiliza(?:mos)?)\s+(?:o|a|os|as)\s+\w+",
    r"(?:versao|versão|version)\s*[:\s]\s*[\d\.]+",
    r"(?:custo|cost|preco|preço)[:\s].*?\$[\d,\.]+",
    r"(?:tabela|table|coluna|column|index)\s+\w+\.\w+",
    r"(?:pr\s*#\d+|PR\s*#\d+|issue\s*#\d+)",
    r"(?:\d+M?\s+(?:linhas|rows|registros))",
]

# Domain tags used to categorize saved memories. These are generic dev defaults —
# customize them for your own project's vocabulary (product names, subsystems,
# services). Patterns are matched case-insensitively; bilingual EN/PT terms are
# fine. A memory gets the top-scoring tags by match count.
TAG_PATTERNS = {
    "architecture": r"architecture|arquitetura|design|refactor|pipeline|pattern",
    "bug-fix": r"\bbug\b|fix(?:ed|ing)?|error|broke|crash|regression|quebr|falh",
    "deploy": r"deploy|release|rollback|merge\b|pr\b|pull.?request|branch|\bci\b",
    "database": r"\bsql\b|postgres|mysql|sqlite|query|schema|migration|index\b",
    "performance": r"performance|slow|timeout|latenc|optimi[zs]|otimi[zs]",
    "infra": r"\binfra\b|docker|kubernet|k8s|nginx|server|cron\b|cloud|aws|gcp",
    "python": r"\bpython\b|pip\b|venv|django|flask|fastapi|pytest",
    "javascript": r"\bjs\b|node|npm|react|vue|next\.?js|typescript|\bts\b",
    "security": r"security|auth\b|token|secret|vuln|cve|encrypt|permission",
    "testing": r"\btest(?:s|ing)?\b|coverage|mock|fixture|assert",
    "api": r"\bapi\b|endpoint|rest\b|graphql|webhook|http",
    "docs": r"\bdocs?\b|readme|documentation|comment",
    "cost": r"\bcost\b|custo|budget|pricing|saving|economia|spend",
    "decision": r"decid|chose|escolh|trade-?off|instead of|rather than|approach",
}

# Trivial patterns — skip saving if the whole turn matches
TRIVIAL_PATTERNS = [
    r"^(?:ok|sim|nao|não|yes|no|certo|entendi|beleza|show|valeu|obrigado|thanks)[\.\!\?]?$",
    r"^(?:continua|continue|prossiga|go ahead|next)[\.\!\?]?$",
]


def extract_sentences(text: str, patterns: list[str], max_results: int = 8) -> list[str]:
    """Extract sentences that match any of the given patterns."""
    results = []
    # Split into sentences (rough but effective)
    sentences = re.split(r"(?<=[.!?\n])\s+", text)
    combined = re.compile("|".join(patterns), re.IGNORECASE)

    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 15 or len(sentence) > 500:
            continue
        if combined.search(sentence):
            # Clean up prefixes like "- ", "* ", "1. "
            clean = re.sub(r"^[\-\*\d]+[\.\)]\s*", "", sentence)
            if clean and clean not in results:
                results.append(clean)
        if len(results) >= max_results:
            break

    return results


def infer_tags(text: str, max_tags: int = 5) -> list[str]:
    """Infer semantic tags from content."""
    lower = text.lower()
    scored = []
    for tag, pattern in TAG_PATTERNS.items():
        matches = len(re.findall(pattern, lower))
        if matches > 0:
            scored.append((tag, matches))

    scored.sort(key=lambda x: -x[1])
    return [tag for tag, _ in scored[:max_tags]]


def is_trivial(turns: list[tuple[str, str]]) -> bool:
    """Check if the conversation is too trivial to save."""
    if not turns:
        return True

    # Total content too short
    total = sum(len(t) for _, t in turns)
    if total < 80:
        return True

    # All user turns are trivial AND assistant is short
    user_turns = [t for r, t in turns if r == "user"]
    assistant_turns = [t for r, t in turns if r == "assistant"]

    if user_turns:
        last_user = user_turns[-1].strip()
        for pattern in TRIVIAL_PATTERNS:
            if re.match(pattern, last_user, re.IGNORECASE):
                if assistant_turns and len(assistant_turns[-1]) < 150:
                    return True

    return False


def extract_insights(turns: list[tuple[str, str]]) -> dict:
    """Main extraction: analyze turns and produce structured output."""
    full_text = "\n\n".join(f"[{r}] {t}" for r, t in turns)
    assistant_text = "\n".join(t for r, t in turns if r == "assistant")
    user_text = "\n".join(t for r, t in turns if r == "user")

    decisions = extract_sentences(assistant_text, DECISION_PATTERNS)
    corrections = extract_sentences(user_text, CORRECTION_PATTERNS)
    facts = extract_sentences(assistant_text, FACT_PATTERNS)

    # Summary = user's question/request (take ALL user turns for context)
    summary_parts = []
    for role, text in turns:
        if role == "user":
            for line in text.split("\n"):
                line = line.strip()
                if len(line) > 15:
                    summary_parts.append(line[:200])
                    break
    summary = " → ".join(summary_parts[:3])

    tags = infer_tags(full_text)

    # Substantial = assistant produced meaningful content
    # Lower bar: 200 chars of cleaned assistant text is worth saving
    worth_saving = bool(
        decisions
        or corrections
        or facts
        or len(assistant_text) > 200
    )

    return {
        "facts": facts,
        "decisions": decisions,
        "corrections": corrections,
        "summary": summary,
        "tags": tags or ["untagged"],
        "worth_saving": worth_saving,
        "assistant_text": assistant_text,
        "user_text": user_text,
    }


def main():
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    if hook_input.get("stop_hook_active"):
        sys.exit(0)

    # Manutenção orgânica throttled (1x/dia): decay de sinapses + prune de dumps
    # antigos desconectados. Isolada — nunca pode quebrar o save. Roda aqui porque o
    # Stop é o ponto async garantido; sem cron externo pra gerenciar.
    try:
        from maintenance import run_if_due
        run_if_due()
    except Exception as e:
        print(f"mcp-memory maintenance error: {e}", file=sys.stderr)

    session_id = hook_input.get("session_id", "")
    transcript_path = hook_input.get("transcript_path", "")

    if not transcript_path or not Path(transcript_path).exists():
        sys.exit(0)

    turns = read_recent_turns(transcript_path)
    if is_trivial(turns):
        sys.exit(0)

    extracted = extract_insights(turns)

    if not extracted.get("worth_saving", False):
        sys.exit(0)

    # Build document — always include condensed conversation content
    parts = []
    if extracted.get("summary"):
        parts.append(f"## Summary\n{extracted['summary']}")

    # Always include condensed assistant response for semantic richness
    assistant_text = extracted.get("assistant_text", "")
    if len(assistant_text) > 200:
        condensed = condense_text(assistant_text, MAX_SAVE_CHARS)
        parts.append(f"## Content\n{condensed}")

    if extracted.get("facts"):
        parts.append("## Facts\n" + "\n".join(f"- {f}" for f in extracted["facts"]))
    if extracted.get("decisions"):
        parts.append("## Decisions\n" + "\n".join(f"- {d}" for d in extracted["decisions"]))
    if extracted.get("corrections"):
        parts.append("## Corrections\n" + "\n".join(f"- {c}" for c in extracted["corrections"]))

    content = "\n\n".join(parts)
    if not content.strip() or len(content.strip()) < 50:
        sys.exit(0)

    # Save to ChromaDB
    try:
        import chromadb

        client = chromadb.PersistentClient(path=DATA_DIR)
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        now = datetime.now(timezone.utc).isoformat()
        doc_id = str(uuid.uuid4())
        tags = extracted.get("tags", [])

        collection.add(
            documents=[content],
            metadatas=[{
                "timestamp": now,
                "source": "claude",
                "role": "hippocampal",
                "session_id": session_id,
                "tags": json.dumps(tags),
            }],
            ids=[doc_id],
        )

    except Exception as e:
        print(f"mcp-memory save error: {e}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
