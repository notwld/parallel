from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from common.ai.graph import build_proposal_graph
from common.ai.providers import FakeProvider, OpenRouterGraphProvider, get_provider


class FakeChat:
    def invoke(self, prompt):
        return SimpleNamespace(content=f'echo:{prompt}')


class AIProviderTests(SimpleTestCase):
    def test_missing_key_uses_fake_provider(self):
        self.assertIsInstance(get_provider(), FakeProvider)
        self.assertEqual(
            get_provider().propose('anything').text,
            '{"operations":[]}',
        )

    @override_settings(OPENROUTER_API_KEY='sk-or-test', OPENROUTER_MODEL='openai/gpt-4o-mini')
    def test_key_selects_openrouter_graph_provider(self):
        self.assertIsInstance(get_provider(), OpenRouterGraphProvider)

    def test_langgraph_proposal_has_no_tools(self):
        graph = build_proposal_graph(FakeChat())
        self.assertEqual(graph.get_graph().nodes.keys(), {'__start__', 'propose', '__end__'})
        result = graph.invoke({'prompt': 'hello'})
        self.assertEqual(result['text'], 'echo:hello')

    @override_settings(OPENROUTER_API_KEY='sk-or-test', OPENROUTER_MODEL='openai/gpt-4o-mini')
    def test_openrouter_provider_uses_graph_without_network(self):
        provider = OpenRouterGraphProvider(chat_model=FakeChat())
        with patch('langchain_openrouter.ChatOpenRouter') as ctor:
            proposal = provider.propose('ping')
        ctor.assert_not_called()
        self.assertEqual(proposal.text, 'echo:ping')
        self.assertEqual(proposal.model, 'openai/gpt-4o-mini')
