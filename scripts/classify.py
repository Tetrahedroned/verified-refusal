#!/usr/bin/env python3
"""verified-refusal classify: heuristic classifier for irreversible actions.

Language-agnostic. No network calls. No LLM. Regex + AST over Python source.
Targets: filepath, 'path::function', plain text description.

CLI:
  python3 classify.py --target 'path/to/file.py::fn_name'
  python3 classify.py --text 'POST /api/payments with amount'
  python3 classify.py --file path/to/file.py
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any

CATEGORIES = (
    "external_api_side_effect",
    "financial_transaction",
    "database_write",
    "file_destructive",
    "message_delivery",
    "webhook_delivery",
    "infrastructure_change",
    "credential_operation",
    "rate_limit_consumption",
    "cache_flush_async",
    "idempotent_violation",
    "lock_escalation",
    "symlink_target",
)


@dataclass
class Rule:
    category: str
    pattern: re.Pattern
    weight: float
    reason: str
    subtle: bool = False


def _c(pat: str) -> re.Pattern:
    return re.compile(pat, re.IGNORECASE | re.MULTILINE)


RULES: list[Rule] = [
    # financial — highest confidence
    Rule("financial_transaction", _c(r"\bstripe\.(charge|paymentintent|refund|transfer|payout|subscription)s?\b"),
         0.98, "stripe payment operation"),
    Rule("financial_transaction", _c(r"\b(paypal|braintree|adyen|square|plaid)\.(charge|capture|transfer|payout)\b"),
         0.97, "payment provider charge/capture"),
    Rule("financial_transaction", _c(r"/(payments?|charges?|transfers?|withdraw(al)?s?|deposits?|invoices?|refunds?)\b"),
         0.85, "financial endpoint path"),
    Rule("financial_transaction", _c(r"\b(authorize|capture|refund|chargeback|wire_transfer|ach_debit)\s*\("),
         0.85, "financial operation verb"),
    Rule("financial_transaction", _c(r"\b(debit|credit)_(account|ledger|wallet)\b"),
         0.88, "ledger operation"),

    # credential
    Rule("credential_operation", _c(r"\b(create|rotate|revoke|delete)_(api_key|token|secret|credential|password)s?\b"),
         0.92, "credential lifecycle"),
    Rule("credential_operation", _c(r"\b(grant|revoke)_(permission|role|access|scope)\b"),
         0.88, "permission grant/revoke"),
    Rule("credential_operation", _c(r"\biam\.(create|delete|attach|detach)_(user|role|policy)\b"),
         0.9, "IAM mutation"),
    Rule("credential_operation", _c(r"\bssh-keygen|gpg\s+--delete-key\b"),
         0.85, "key material mutation"),

    # external api side-effect
    Rule("external_api_side_effect", _c(r"\b(requests|httpx|aiohttp|urllib3)\.(post|put|delete|patch)\b"),
         0.9, "HTTP mutation verb"),
    Rule("external_api_side_effect", _c(r"\b(session|client)\.(post|put|delete|patch)\s*\("),
         0.85, "session/client HTTP mutation"),
    Rule("external_api_side_effect", _c(r"\bfetch\s*\([^)]*method\s*:\s*['\"](POST|PUT|DELETE|PATCH)['\"]"),
         0.88, "fetch with mutation method"),
    Rule("external_api_side_effect", _c(r"\bXMLHttpRequest.*\.open\s*\(\s*['\"](POST|PUT|DELETE|PATCH)"),
         0.82, "XHR mutation method"),
    Rule("external_api_side_effect", _c(r"\bcurl\s+(?:-X\s+)?(?:-X)?\s*['\"]?(POST|PUT|DELETE|PATCH)"),
         0.8, "curl mutation method"),
    Rule("external_api_side_effect", _c(r"\bHttpClient\.(Post|Put|Delete|Patch)Async\b"),
         0.85, "HttpClient mutation"),

    # database write
    Rule("database_write", _c(r"\b(INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|TRUNCATE|DROP\s+(TABLE|INDEX|DATABASE)|ALTER\s+TABLE)\b"),
         0.95, "SQL DDL/DML"),
    Rule("database_write", _c(r"\b(cursor|conn|db|session)\.execute(many)?\s*\(\s*['\"](INSERT|UPDATE|DELETE|TRUNCATE|DROP|ALTER)"),
         0.92, "cursor.execute mutation"),
    Rule("database_write", _c(r"\bsession\.(add|delete|merge|commit)\s*\("),
         0.85, "SQLAlchemy write session"),
    Rule("database_write", _c(r"\b\w+\.(save|create|update|destroy|delete)\s*\("),
         0.6, "ORM write method (weak signal)"),
    Rule("database_write", _c(r"\bMongo(Client)?.*\.(insert|update|delete|drop|replace|find_and_modify)"),
         0.9, "MongoDB mutation"),
    Rule("database_write", _c(r"\b(redis|r)\.(set|del|flushdb|flushall|hset|rpush|lpush|sadd|zadd|expire)\s*\("),
         0.82, "redis mutation"),
    Rule("database_write", _c(r"\bboto3.*\.(put_item|update_item|delete_item|batch_write_item)\b"),
         0.9, "DynamoDB mutation"),

    # file destructive
    Rule("file_destructive", _c(r"\bos\.(remove|unlink|rmdir)\s*\("),
         0.95, "os file deletion"),
    Rule("file_destructive", _c(r"\bshutil\.(rmtree|move)\s*\("),
         0.95, "shutil destructive"),
    Rule("file_destructive", _c(r"\b(Path|pathlib\.Path)\([^)]*\)\.(unlink|rmdir)\b"),
         0.92, "pathlib delete"),
    Rule("file_destructive", _c(r"\bopen\s*\([^)]*,\s*['\"](w|wb|w\+|wb\+)['\"]"),
         0.7, "open with truncating mode"),
    Rule("file_destructive", _c(r"\bsubprocess\.(run|Popen|call|check_call)\s*\([^)]*['\"]rm\s+-(r|rf|f)"),
         0.95, "shell rm via subprocess"),
    Rule("file_destructive", _c(r"\bfs\.(unlink|rmdir|rm|writeFile|writeFileSync|truncate)\b"),
         0.88, "node fs destructive"),
    Rule("file_destructive", _c(r"\bos\.rename\s*\("),
         0.75, "os.rename (overwrites target)"),

    # message delivery
    Rule("message_delivery", _c(r"\b(smtplib|smtp)\..*\.(sendmail|send_message)\b"),
         0.95, "smtp send"),
    Rule("message_delivery", _c(r"\btwilio.*messages\.create\b"),
         0.95, "twilio SMS"),
    Rule("message_delivery", _c(r"\b(slack|discord)(_\w+)?(\.chat)?\.post_?[Mm]essage\b"),
         0.93, "chat post"),
    Rule("message_delivery", _c(r"\bsendgrid|mailgun|postmark|ses\b.*\.(send|mail)"),
         0.9, "email provider"),
    Rule("message_delivery", _c(r"\b(fcm|apns|expo)\.(send|push)\b"),
         0.88, "push notification"),
    Rule("message_delivery", _c(r"\bboto3.*ses.*send_(email|raw_email|bulk)"),
         0.92, "AWS SES send"),

    # webhook
    Rule("webhook_delivery", _c(r"/webhooks?/|/hooks?/|webhook_url\b|incoming_webhook\b"),
         0.82, "webhook endpoint"),
    Rule("webhook_delivery", _c(r"\b(register|create)_webhook\b|webhook\.create\b"),
         0.88, "webhook registration"),
    Rule("webhook_delivery", _c(r"\b\w*webhook\w*\.(create|register|add|subscribe)\b"),
         0.88, "webhook endpoint registration"),

    # infrastructure
    Rule("infrastructure_change", _c(r"\bterraform\s+(apply|destroy)|pulumi\s+up\b"),
         0.97, "IaC apply"),
    Rule("infrastructure_change", _c(r"\bkubectl\s+(apply|delete|replace|scale|rollout)\b"),
         0.92, "kubectl mutation"),
    Rule("infrastructure_change", _c(r"\baws\s+(ec2|s3|iam|rds|lambda)\s+(create|delete|terminate|modify|put)"),
         0.93, "aws cli mutation"),
    Rule("infrastructure_change", _c(r"\bgcloud\s+\w+\s+(create|delete|update)|az\s+\w+\s+(create|delete|update)"),
         0.9, "gcloud/az mutation"),
    Rule("infrastructure_change", _c(r"\bdocker\s+(run|kill|rm|rmi|push)\b"),
         0.8, "docker mutation"),
    Rule("infrastructure_change", _c(r"\broute53\.(change|change_resource_record_sets)|dns.*(create|delete|update)_record\b"),
         0.93, "DNS record mutation"),
    Rule("infrastructure_change", _c(r"\bcertbot|acme.*issue|lets-?encrypt\b"),
         0.85, "certificate issuance"),
    # boto3 / AWS SDK client mutations. Matches `ec2.run_instances(...)`,
    # `s3.delete_bucket(...)`, `route53.change_resource_record_sets(...)`.
    Rule("infrastructure_change", _c(r"\b(ec2|s3|rds|elb|elbv2|route53|iam|lambda|sns|sqs|dynamodb|cloudformation|eks|ecs|autoscaling)(_client)?\.(create_\w+|delete_\w+|put_\w+|run_\w+|terminate_\w+|modify_\w+|change_\w+|update_\w+|attach_\w+|detach_\w+)\b"),
         0.92, "AWS SDK client mutation"),

    # cache flush async (subtle — looks local but replicates)
    Rule("cache_flush_async", _c(r"\b(cache|cdn|varnish|fastly|cloudflare)\.(purge|invalidate|flush|ban)\b"),
         0.9, "CDN/cache purge replicates externally", subtle=True),
    Rule("cache_flush_async", _c(r"\bmemcached.*\bflush_all\b|redis.*\bflushall\b"),
         0.88, "cache flush (replicates in cluster)", subtle=True),

    # idempotent violation (subtle)
    Rule("idempotent_violation", _c(r"\brequests\.post\b(?!.*idempotency)"),
         0.55, "POST without detected idempotency key", subtle=True),

    # lock escalation (subtle)
    Rule("lock_escalation", _c(r"\bSELECT\b[^;]*\bFOR\s+UPDATE\b"),
         0.8, "SELECT FOR UPDATE escalates lock", subtle=True),
    Rule("lock_escalation", _c(r"\bLOCK\s+TABLE\b"),
         0.85, "explicit LOCK TABLE", subtle=True),

    # symlink (subtle — file op on possibly-symlinked path)
    Rule("symlink_target", _c(r"\bos\.(readlink|symlink|lchown|lstat)\b"),
         0.7, "symlink-adjacent operation", subtle=True),

    # rate limit (subtle) — signaled by comments/decorators or known APIs
    Rule("rate_limit_consumption", _c(r"\b(rate[_-]?limit|quota|throttle)\b"),
         0.55, "rate-limited operation (consumes quota on failure)", subtle=True),
]


SAFE_HINTS = (
    _c(r"\b(requests|httpx|aiohttp|fetch)\b.*\b(get|head)\b"),
    _c(r"\bSELECT\b(?!.*\bFOR\s+UPDATE\b)"),
    _c(r"\bos\.(stat|path\.(exists|isdir|isfile|getsize))\b"),
    _c(r"\bopen\s*\([^)]*,\s*['\"](r|rb)['\"]"),
)

GATE_MARKERS = (
    "VERIFIED_REFUSAL_MODE",
    "VERIFIED_REFUSAL_OVERRIDE",
    "verified_refusal_gate",
    "vr_gate(",
    "@vr_gate",
)


@dataclass
class Hit:
    category: str
    weight: float
    reason: str
    subtle: bool = False


def _score(text: str) -> list[Hit]:
    hits: list[Hit] = []
    for rule in RULES:
        if rule.pattern.search(text):
            hits.append(Hit(rule.category, rule.weight, rule.reason, rule.subtle))
    return hits


def _has_gate(text: str) -> bool:
    return any(marker in text for marker in GATE_MARKERS)


# Specific categories beat the catch-all. Ordering: higher index = more specific.
# When multiple categories match, a more-specific one wins even if its best-hit
# weight is slightly lower than the catch-all's.
_CATEGORY_SPECIFICITY = {c: i for i, c in enumerate([
    "external_api_side_effect",    # catch-all for HTTP mutations
    "rate_limit_consumption",
    "cache_flush_async",
    "idempotent_violation",
    "symlink_target",
    "lock_escalation",
    "webhook_delivery",
    "message_delivery",
    "database_write",
    "file_destructive",
    "infrastructure_change",
    "credential_operation",
    "financial_transaction",
])}


def _category_winner(hits: list[Hit]) -> tuple[str | None, float]:
    if not hits:
        return None, 0.0
    non_subtle = [h for h in hits if not h.subtle]
    pool = non_subtle or hits
    # score = weight primarily, specificity as tiebreaker within 0.15 of top
    top_weight = max(h.weight for h in pool)
    contenders = [h for h in pool if h.weight >= top_weight - 0.15]
    best = max(
        contenders,
        key=lambda h: (_CATEGORY_SPECIFICITY.get(h.category, 0), h.weight),
    )
    # confidence boost if subtle risks stack on top of a non-subtle hit
    subtle_bonus = 0.05 * len([h for h in hits if h.subtle and h.category != best.category])
    confidence = min(1.0, best.weight + subtle_bonus)
    return best.category, confidence


def _reversibility_window(category: str) -> str | None:
    windows = {
        "file_destructive": "none (without backup)",
        "database_write": "transaction window if uncommitted",
        "message_delivery": "none — recipient has received",
        "webhook_delivery": "none — receiver has processed",
        "financial_transaction": "may have settlement window (varies by provider)",
        "external_api_side_effect": "depends on provider",
        "credential_operation": "none for rotations; short for revocations",
        "infrastructure_change": "rollback possible but costly",
    }
    return windows.get(category)


def _subtle_risks(hits: list[Hit]) -> list[str]:
    seen: list[str] = []
    for h in hits:
        if h.subtle and h.reason not in seen:
            seen.append(h.reason)
    return seen


def _safe_only(text: str, hits: list[Hit]) -> bool:
    if hits:
        return False
    return any(p.search(text) for p in SAFE_HINTS)


def classify(target: str, context: str | None = None) -> dict[str, Any]:
    """Classify a target. target: filepath, 'file::fn', or raw text."""
    text, source = _resolve_target(target, context)
    hits = _score(text)
    category, confidence = _category_winner(hits)
    irreversible = category is not None and confidence >= 0.5
    if not irreversible and _safe_only(text, hits):
        return {
            "irreversible": False,
            "confidence": 0.9,
            "category": None,
            "reason": "only read-only / safe patterns detected",
            "reversibility_window": None,
            "subtle_risks": [],
            "recommended_gate": "none",
            "source": source,
        }
    reason = hits[0].reason if hits else "no mutating or side-effectful patterns matched"
    if category:
        reason = next((h.reason for h in hits if h.category == category), reason)
    gate = (
        "verified_refusal"
        if irreversible
        else ("review" if hits else "none")
    )
    return {
        "irreversible": irreversible,
        "confidence": round(confidence, 3),
        "category": category,
        "reason": reason,
        "reversibility_window": _reversibility_window(category) if category else None,
        "subtle_risks": _subtle_risks(hits),
        "recommended_gate": gate,
        "source": source,
    }


def _resolve_target(target: str, context: str | None) -> tuple[str, str]:
    """Resolve target to (text, source_label)."""
    if context:
        return (target + "\n" + context, "text+context")
    if "::" in target and os.path.isfile(target.split("::", 1)[0]):
        path, fn = target.split("::", 1)
        src = _read(path)
        body = _extract_function(src, fn, path)
        return (body or src, f"{path}::{fn}")
    if os.path.isfile(target):
        return (_read(target), target)
    return (target, "text")


def _read(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def _extract_function(src: str, name: str, path: str) -> str | None:
    if path.endswith(".py"):
        try:
            tree = ast.parse(src)
        except SyntaxError:
            return None
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                start = node.lineno - 1
                end = getattr(node, "end_lineno", None) or start + 1
                return "\n".join(src.splitlines()[start:end])
        return None
    # naive extraction for JS/TS/bash — function keyword / arrow / bash function
    lines = src.splitlines()
    patterns = [
        re.compile(rf"function\s+{re.escape(name)}\b"),
        re.compile(rf"\b{re.escape(name)}\s*=\s*(async\s*)?\([^)]*\)\s*=>"),
        re.compile(rf"\b{re.escape(name)}\s*\(\)\s*\{{"),  # bash
        re.compile(rf"\bdef\s+{re.escape(name)}\b"),
    ]
    for i, line in enumerate(lines):
        if any(p.search(line) for p in patterns):
            # grab until blank line or next top-level def — best-effort
            chunk = [line]
            depth = line.count("{") - line.count("}")
            for j in range(i + 1, min(len(lines), i + 120)):
                chunk.append(lines[j])
                depth += lines[j].count("{") - lines[j].count("}")
                if depth <= 0 and lines[j].strip() == "":
                    break
            return "\n".join(chunk)
    return None


def classify_file(path: str) -> dict[str, Any]:
    """Classify every function in a file."""
    src = _read(path)
    results: list[dict[str, Any]] = []
    if path.endswith(".py"):
        try:
            tree = ast.parse(src)
        except SyntaxError:
            return {"file": path, "error": "syntax_error", "results": []}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = node.lineno - 1
                end = getattr(node, "end_lineno", None) or start + 1
                body = "\n".join(src.splitlines()[start:end])
                r = classify(body)
                r["function"] = node.name
                r["line"] = node.lineno
                r["gated"] = _has_gate(body)
                results.append(r)
    else:
        # best-effort per-function for JS/bash
        fn_rx = re.compile(r"(?:function\s+(\w+)|(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>|(\w+)\s*\(\)\s*\{)")
        lines = src.splitlines()
        for i, line in enumerate(lines):
            m = fn_rx.search(line)
            if not m:
                continue
            name = m.group(1) or m.group(2) or m.group(3)
            if not name:
                continue
            body = _extract_function(src, name, path) or line
            r = classify(body)
            r["function"] = name
            r["line"] = i + 1
            r["gated"] = _has_gate(body)
            results.append(r)
    return {"file": path, "results": results}


def _cli() -> int:
    ap = argparse.ArgumentParser(description="verified-refusal classifier")
    ap.add_argument("--target", help="filepath or 'file::function'")
    ap.add_argument("--text", help="raw text description")
    ap.add_argument("--file", help="classify every function in a file")
    ap.add_argument("--context", help="optional context text")
    args = ap.parse_args()

    if args.file:
        out = classify_file(args.file)
    elif args.target:
        out = classify(args.target, args.context)
    elif args.text:
        out = classify(args.text, args.context)
    else:
        ap.print_help()
        return 2
    json.dump(out, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
