"""Shared fake Gemini client for tests, so no test hits the network by
default. Mirrors just enough of the google-genai response shape
(`client.models.generate_content(...).text`) for our classifiers.
"""


class FakeGeminiResponse:
    def __init__(self, text: str):
        self.text = text


class FakeGeminiClient:
    """Returns a fixed response, or raises if `raise_error` is set."""

    def __init__(self, response_text: str = "", raise_error: Exception | None = None):
        self._response_text = response_text
        self._raise_error = raise_error
        self.calls: list[dict] = []

        class _Models:
            def __init__(self, outer: "FakeGeminiClient"):
                self._outer = outer

            def generate_content(self, model: str, contents: str):
                self._outer.calls.append({"model": model, "contents": contents})
                if self._outer._raise_error:
                    raise self._outer._raise_error
                return FakeGeminiResponse(self._outer._response_text)

        self.models = _Models(self)
