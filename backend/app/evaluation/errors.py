class LLMError(Exception):
    def __init__(self, message: str, *, code: str, transient: bool, latency_ms: int | None = None):
        super().__init__(message)
        self.code = code
        self.transient = transient
        self.latency_ms = latency_ms


class LLMTimeout(LLMError):
    def __init__(self, message: str = "model call timed out", *, latency_ms: int | None = None):
        super().__init__(message, code="timeout", transient=True, latency_ms=latency_ms)


class LLMProviderError(LLMError):
    pass
