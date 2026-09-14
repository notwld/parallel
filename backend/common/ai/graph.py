from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class ProposalState(TypedDict):
    prompt: str
    text: str


def build_proposal_graph(chat_model):
    """One-node graph: model proposes text. No tools, DB, or network from the model."""

    def propose(state: ProposalState) -> ProposalState:
        message = chat_model.invoke(state['prompt'])
        content = message.content
        if not isinstance(content, str):
            content = str(content)
        return {'prompt': state['prompt'], 'text': content}

    graph = StateGraph(ProposalState)
    graph.add_node('propose', propose)
    graph.add_edge(START, 'propose')
    graph.add_edge('propose', END)
    return graph.compile()
