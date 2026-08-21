#!/usr/bin/env python3
"""
Apply suggested seccomp syscalls to .mammoth/seccomp.json and create a draft PR.

This script is intended to run in CI and requires:
- git configured (actions/checkout used)
- gh CLI authenticated (or GITHUB_TOKEN env)
- write access to push branches

Behavior:
- Read diagnostics/suggestion.json
- If suggestions exist, update .mammoth/seccomp.json by appending missing syscall names
- Create a branch 'seccomp-tweak-<timestamp>' and commit the change with Co-authored-by trailer
- Push branch and open a draft PR against the default branch (main)

The script is conservative: it will not run if no suggestions or if .mammoth/seccomp.json missing.
"""
import json
import os
import subprocess
import sys
from datetime import datetime

DIAG = 'diagnostics/suggestion.json'
SECCOMP = '.mammoth/seccomp.json'

if not os.path.exists(DIAG):
    print('No suggestion file found, nothing to do')
    sys.exit(0)

with open(DIAG, 'r', encoding='utf-8') as fh:
    j = json.load(fh)
    suggestions = j.get('suggestions', [])

if not suggestions:
    print('No suggestions, nothing to do')
    sys.exit(0)

if not os.path.exists(SECCOMP):
    print('.mammoth/seccomp.json not found; aborting')
    sys.exit(1)

# load seccomp
with open(SECCOMP, 'r', encoding='utf-8') as fh:
    sec = json.load(fh)

# find the first syscall allow list object
if 'syscalls' not in sec or not isinstance(sec['syscalls'], list) or not sec['syscalls']:
    print('seccomp.json missing syscalls array; aborting')
    sys.exit(1)

# use the first entry's names list (common pattern)
entry = sec['syscalls'][0]
names = entry.get('names', [])
changed = False
for s in suggestions:
    if s not in names:
        names.append(s)
        changed = True

if not changed:
    print('No changes to seccomp.json needed')
    sys.exit(0)

# write updated seccomp to a new branch
branch = f'seccomp-tweak-{datetime.utcnow().strftime("%Y%m%d%H%M%S")}'
new_file = SECCOMP
with open(new_file, 'w', encoding='utf-8') as fh:
    json.dump(sec, fh, indent=2, ensure_ascii=False)

# git operations
subprocess.check_call(['git', 'config', 'user.email', 'action@github.com'])
subprocess.check_call(['git', 'config', 'user.name', 'github-action'])
subprocess.check_call(['git', 'checkout', '-b', branch])
subprocess.check_call(['git', 'add', new_file])
commit_msg = ('Apply suggested seccomp tweaks from CI tuner\n\n'
              'Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>')
subprocess.check_call(['git', 'commit', '-m', commit_msg])
# push
remote = os.environ.get('GITHUB_REPOSITORY')
if remote:
    # push to origin
    subprocess.check_call(['git', 'push', '--set-upstream', 'origin', branch])
else:
    subprocess.check_call(['git', 'push', '--set-upstream', 'origin', branch])

# create PR draft using gh if available
try:
    pr_title = 'CI: Suggested seccomp tweaks (automation)'
    pr_body = 'This PR adds minimal syscall allow-list entries suggested by the CI seccomp tuner. Please review before merging.'
    subprocess.check_call(['gh', 'pr', 'create', '--title', pr_title, '--body', pr_body, '--base', 'main', '--head', branch, '--draft'])
    print('Created draft PR')
except Exception as e:
    print('Failed to create PR with gh CLI:', e)
    print('You can create a PR manually from branch:', branch)
    sys.exit(0)
