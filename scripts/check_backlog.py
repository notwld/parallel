"""Validate the portable Markdown backlog and show currently eligible work."""
from pathlib import Path
import re


def main():
    root = Path(__file__).resolve().parent.parent
    source = (root / 'TASKS.md').read_text(encoding='utf-8')
    tasks = {}
    for block in re.split(r'^### ', source, flags=re.MULTILINE)[1:]:
        task_id = re.match(r'(P\d{3})\b', block)
        assert task_id, 'Every task heading needs a stable Pnnn ID'
        task_id = task_id.group(1)
        assert task_id not in tasks, f'Duplicate task: {task_id}'
        status = re.search(r'^Status: (\w+)$', block, re.MULTILINE)
        deps = re.search(r'^Depends on: (.+)$', block, re.MULTILINE)
        assert status and deps, f'Missing status/dependencies: {task_id}'
        assert status[1] in {'todo', 'in_progress', 'blocked', 'done', 'deferred'}, task_id
        dependency_text = deps[1]
        assert dependency_text == 'none' or re.fullmatch(r'P\d{3}(, P\d{3})*', dependency_text), task_id
        tasks[task_id] = (status[1], re.findall(r'P\d{3}', dependency_text))
    assert tasks, 'No tasks found'
    visited, active = set(), set()

    def visit(task_id):
        assert task_id in tasks, f'Unknown dependency: {task_id}'
        assert task_id not in active, f'Dependency cycle involving {task_id}'
        if task_id in visited:
            return
        active.add(task_id)
        status, dependencies = tasks[task_id]
        for dep in dependencies:
            visit(dep)
            if status in {'done', 'in_progress'}:
                assert tasks[dep][0] == 'done', f'{task_id} started before {dep} completed'
        active.remove(task_id)
        visited.add(task_id)

    for task_id in tasks:
        visit(task_id)
    for path in ['AGENTS.md', 'CLAUDE.md', 'docs/HANDOFF.md', 'docs/STATUS.md',
                 'docs/PRODUCT.md', 'docs/DECISIONS.md', 'docs/ARCHITECTURE.md',
                 'docs/source/specification.md', 'docs/WORKLOG.md']:
        assert (root / path).is_file(), f'Missing handoff file: {path}'
    print(f'Validated {len(tasks)} tasks; no missing or cyclic dependencies.')
    for task_id, (status, deps) in tasks.items():
        if status == 'in_progress':
            print(f'Resume: {task_id}')
        elif status == 'todo' and all(tasks[dep][0] == 'done' for dep in deps):
            print(f'Ready: {task_id}')


if __name__ == '__main__':
    main()
