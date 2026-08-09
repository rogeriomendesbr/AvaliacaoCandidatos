from huggingface_hub import InferenceClient
from huggingface_hub.errors import HfHubHTTPError


class RateLimitError(Exception):
    pass


class AuthenticationError(Exception):
    pass


class TokenLimitError(Exception):
    pass


class APIError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


# Estimativa grosseira de tokens (~4 caracteres por token) usada apenas para
# rejeitar prompts claramente grandes demais antes de chamar a API.
_CHARS_PER_TOKEN = 4
_MAX_PROMPT_TOKENS = 100_000


def estimate_tokens(text: str) -> int:
    return len(text) // _CHARS_PER_TOKEN


def build_prompt(prompt_template: str, requirements: str, resumes: dict) -> str:
    text_resumes = "\n\n- ".join(resumes.values())
<<<<<<< HEAD
    prompt = f"{prompt_template}\n\n**REQUISITOS DA VAGA:**\n\n{requirements}\n\n**CURRÍCULOS DOS CANDIDATOS:**\n\n- {text_resumes}"
    if estimate_tokens(prompt) > _MAX_PROMPT_TOKENS:
        raise TokenLimitError()
    return prompt
=======
    return f"{prompt_template}\n\n**REQUISITOS DA VAGA:**\n\n{requirements}\n\n**CURRÍCULOS DOS CANDIDATOS:**\n\n- {text_resumes}"
>>>>>>> 50e682b16ee4c81eb52b1fcf5ada1b47412b0702


def analyze_resumes(api_key: str, model: str, prompt: str) -> str:
    client = InferenceClient(api_key=api_key)
    try:
        response = client.chat_completion(
            model=model,
            messages=[
                {"role": "system", "content": "Você é um assistente prestativo."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=2048,
        )
        return response.choices[0].message.content
    except HfHubHTTPError as e:
        status = e.response.status_code if hasattr(e, "response") and e.response is not None else 0
        msg = str(e).lower()
        if status == 401 or status == 403:
            raise AuthenticationError() from e
        if status == 429:
            raise RateLimitError() from e
        if status == 413 or "too large" in msg or ("token" in msg and "limit" in msg):
            raise TokenLimitError() from e
        raise APIError(str(e)) from e


__all__ = ["analyze_resumes", "build_prompt", "estimate_tokens", "RateLimitError", "AuthenticationError", "APIError", "TokenLimitError"]
