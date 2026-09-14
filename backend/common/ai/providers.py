from dataclasses import dataclass

from django.conf import settings


@dataclass(frozen=True)
class Proposal:
    text: str
    model: str


class FakeProvider:
    model = 'fake'

    def propose(self, prompt: str) -> Proposal:
        return Proposal(text='{"operations":[]}', model=self.model)


class OpenRouterGraphProvider:
    def __init__(self, chat_model=None):
        self._chat_model = chat_model
        self._graph = None

    def _model(self):
        if self._chat_model is None:
            from langchain_openrouter import ChatOpenRouter

            self._chat_model = ChatOpenRouter(
                model=settings.OPENROUTER_MODEL,
                api_key=settings.OPENROUTER_API_KEY,
                temperature=0,
                timeout=settings.OPENROUTER_TIMEOUT_MS,
                max_retries=0,
                app_title='Parallel',
            )
        return self._chat_model

    def _compiled(self):
        if self._graph is None:
            from common.ai.graph import build_proposal_graph

            self._graph = build_proposal_graph(self._model())
        return self._graph

    def propose(self, prompt: str) -> Proposal:
        result = self._compiled().invoke({'prompt': prompt})
        return Proposal(text=result['text'], model=settings.OPENROUTER_MODEL)


def get_provider():
    if settings.OPENROUTER_API_KEY:
        return OpenRouterGraphProvider()
    return FakeProvider()
