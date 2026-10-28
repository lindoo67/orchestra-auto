#!/usr/bin/env python3
"""Create a reproducible DEMO in a new external directory; never overwrite a run."""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', required=True)
    parser.add_argument('--target-repo', default=str(Path.cwd()))
    args = parser.parse_args()
    script = Path(__file__).with_name('progress.py')
    records = [
        ('init', {'id': 'demo-run', 'title': 'DEMO · offline progress scenarios',
                  'target_repo': args.target_repo, 'mode': 'DEMO',
                  'phase': 'acceptance', 'status': 'active'}),
        ('task', {'id': 'core', 'title': 'Protocol implementation', 'status': 'accepted'}),
        ('task', {'id': 'view', 'title': 'Local dashboard', 'dependencies': ['core'],
                  'status': 'running'}),
        ('task', {'id': 'docs', 'title': 'Documentation', 'dependencies': ['view'],
                  'status': 'blocked', 'blocked_reason': 'Waiting for dashboard acceptance'}),
        ('task', {'id': 'decision', 'title': 'User decision', 'status': 'waiting_user',
                  'pending_decision': 'DEMO: choose release timing'}),
        ('task', {'id': 'retry', 'title': 'Failed review sent back', 'status': 'rejected',
                  'blocked_reason': 'DEMO: fix missing recovery evidence'}),
        ('worker', {'id': 'top', 'task_id': 'view', 'dispatch_id': 'demo-dispatch',
                    'attempt': 1, 'worktree': 'demo-view', 'start_confirmation': 'observed',
                    'lifecycle': 'running'}),
        ('worker', {'id': 'nested', 'task_id': 'view', 'dispatch_id': 'demo-nested',
                    'attempt': 1, 'parent_worker_id': 'top', 'worktree': 'demo-nested',
                    'start_confirmation': 'unobserved', 'lifecycle': 'lost'}),
        ('delivery', {'task_id': 'core', 'implemented': True, 'integrated': True,
                      'merged': False, 'tracker_closed': False}),
        ('artifact', {'id': 'test-report', 'task_id': 'core', 'kind': 'test',
                      'label': 'DEMO test reference (illustrative)', 'reference': 'demo-tests.txt'}),
        ('artifact', {'id': 'sample-pr', 'task_id': 'core', 'kind': 'pr',
                      'label': 'DEMO PR reference (illustrative)',
                      'reference': 'https://example.com/demo/pull/1'}),
        ('event', {'type': 'review_rejected', 'task_id': 'retry',
                   'summary': 'DEMO review failed; coordinator requested corrections',
                   'evidence': ['demo-review.txt']}),
    ]
    # A second invocation cannot replay init and then overwrite subsequent REAL data.
    state = Path(args.state).expanduser()
    if state.exists():
        parser.error('demo requires a new state directory; never reuse REAL or existing DEMO data')
    for index, (command, data) in enumerate(records):
        result = subprocess.run([sys.executable, str(script), '--state', args.state, command,
                                 '--event-id', 'demo-' + str(index), '--data', json.dumps(data)])
        if result.returncode:
            return result.returncode
    print('DEMO ready. Serve this directory with progress.py --state STATE serve')
    return 0


if __name__ == '__main__':
    sys.exit(main())
