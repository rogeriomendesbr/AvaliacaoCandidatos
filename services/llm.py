import re

import groq
from groq import Groq


class RateLimitError(Exception):
    pass


class AuthenticationError(Exception):
    pass


class TokenLimitError(Exception):
    pass


class PromptInjectionError(Exception):
    pass


class APIError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


# Estimativa grosseira de tokens (~4 caracteres por token) usada apenas para
# rejeitar prompts claramente grandes demais antes de chamar a API.
_CHARS_PER_TOKEN = 4
_MAX_PROMPT_TOKENS = 100_000

# Caracteres invisíveis usados para esconder texto de instrução dentro de um
# currículo (o texto renderizado parece normal, mas o modelo ainda o lê).
_ZERO_WIDTH_CHARS = "​‌‍﻿⁠"

# Heurística, não uma defesa perfeita: cobre tentativas comuns de fazer o
# modelo ignorar as instruções do prompt ou se auto-atribuir uma nota alta.
# Complementa (não substitui) o aviso de segurança em prompts/analysis.md.
_INJECTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    for pattern in (
        r"ignore\s+(all\s+|every\s+)?(the\s+)?(previous|above|prior)\s+instructions",
        r"disregard\s+(the\s+)?(previous|above|prior)\s+instructions",
        r"ignor(e|ando)\s+(todas\s+as\s+|as\s+)?instru[cç][õo]es\s+(anteriores|acima)",
        r"desconsidere\s+(as\s+)?instru[cç][õo]es\s+(anteriores|acima)",
        r"you\s+are\s+now\s+(a|an)\b",
        r"a\s+partir\s+de\s+agora\s+voc[êe]\s+[ée]\s+(um|uma)\b",
        r"\bnova\s+instru[cç][ãa]o\s*:",
        r"<\|[^|]*\|>",
        r"\[(system|inst)\]",
        r"^\s*system\s*:",
        r"give\s+.{0,20}?100\s*%",
        r"atribua\s+(a\s+)?nota\s+(m[áa]xima|100)\b",
        r"aprove\s+(este|esse)\s+candidato\s+(automaticamente|sempre)?",
        r"sempre\s+aprove",
    )
]


def estimate_tokens(text: str) -> int:
    return len(text) // _CHARS_PER_TOKEN


def check_prompt_injection(text: str) -> None:
    if any(char in text for char in _ZERO_WIDTH_CHARS):
        raise PromptInjectionError()
    if any(pattern.search(text) for pattern in _INJECTION_PATTERNS):
        raise PromptInjectionError()


def build_prompt(prompt_template: str, requirements: str, resumes: dict[str, str]) -> str:
    for resume_text in resumes.values():
        check_prompt_injection(resume_text)
    text_resumes = "\n\n- ".join(resumes.values())
    prompt = f"{prompt_template}\n\n**REQUISITOS DA VAGA:**\n\n{requirements}\n\n**CURRÍCULOS DOS CANDIDATOS:**\n\n- {text_resumes}"
    if estimate_tokens(prompt) > _MAX_PROMPT_TOKENS:
        raise TokenLimitError()
    return prompt


def analyze_resumes(api_key: str, model: str, prompt: str) -> str:
    client = Groq(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Você é um assistente prestativo."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=2048,
        )
        return response.choices[0].message.content
    except (groq.AuthenticationError, groq.PermissionDeniedError) as e:
        raise AuthenticationError() from e
    except groq.RateLimitError as e:
        raise RateLimitError() from e
    except groq.APIStatusError as e:
        msg = str(e).lower()
        if e.status_code == 413 or "too large" in msg or "context" in msg or ("token" in msg and "limit" in msg):
            raise TokenLimitError() from e
        raise APIError(str(e)) from e
    except groq.APIConnectionError as e:
        raise APIError(str(e)) from e


__all__ = [
    "analyze_resumes",
    "build_prompt",
    "check_prompt_injection",
    "estimate_tokens",
    "RateLimitError",
    "AuthenticationError",
    "APIError",
    "TokenLimitError",
    "PromptInjectionError",
]
