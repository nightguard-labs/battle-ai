"""Uncensored / unaligned models get ZERO tools. In Battle AI they may only fight inside the no-network cage,
and only when their roster entry says cage_exception: true."""
import re
_UNCENSORED_PATTERNS = re.compile(
    r"uncensored|unfiltered|unsafe|unaligned|abliterated|de-?censor"
    r"|heretic|dolphin|wizardlm-uncensored|jailbreak|toxic|evil[-_]?twin"
    r"|no-?guardrails?|without-?guardrails?", re.I)


def is_model_blocked(model_name) -> bool:
    return bool(model_name) and bool(_UNCENSORED_PATTERNS.search(model_name))
