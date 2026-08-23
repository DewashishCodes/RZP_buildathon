"""Shared fake Gemini client for tests, so no test hits the network by
default. Mirrors just enough of the google-genai response shape
(`client.models.generate_content(...).text`) for our classifiers.
"""
from google.genai import errors


class FakeAPIError(errors.APIError):
    """A constructible stand-in for google.genai.errors.APIError - the real
    class requires a requests.Response to build, which tests shouldn't need
    to fabricate just to simulate a quota/network failure.
    """

    def __init__(self, message: str = "429 RESOURCE_EXHAUSTED (fake)"):
        Exception.__init__(self, message)


class FakeGeminiResponse:
    def __init__(self, text: str):
        self.text = text


class FakeGeminiClient:
    """Returns a fixed response, or raises `raise_error` if set (e.g. a
    google.genai.errors.APIError to simulate a quota/network failure)."""

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
