#!/usr/bin/env python3
"""
Simple CI helper that inspects runtime_info.txt and suggests additional syscalls
to add to the seccomp profile if Python fails to start under the profile.

This script is intended to run in CI after the docker sandbox job captures runtime_info.txt
and writes any stderr to runtime_error.txt (optional).

It produces diagnostics/suggestion.json and diagnostics/diagnostics.txt in the workspace.

Usage (CI):
  python .github/scripts/ci_seccomp_tuner.py --runtime runtime_info.txt --stderr runtime_error.txt --out diagnostics

"""
import argparse
import json
import os
import re

# curated fallback syscalls to consider if missing; ordered by likelihood for python runtime
CANDIDATE_SYSCALLS = [
    "madvise", "mprotect", "mremap", "set_tid_address", "prctl", "arch_prctl",
    "setxattr", "getxattr", "lseek", "statx",
]

RE_SEC_COMP = re.compile(r"Seccomp:\s*(\d+)", re.IGNORECASE)
RE_CAPEFF = re.compile(r"CapEff:\s*([0-9a-fA-Fx]+)")
# Linux capabilities mapping (partial, common set)
CAPABILITY_NAMES = [
    'CAP_CHOWN','CAP_DAC_OVERRIDE','CAP_DAC_READ_SEARCH','CAP_FOWNER','CAP_FSETID',
    'CAP_KILL','CAP_SETGID','CAP_SETUID','CAP_SETPCAP','CAP_LINUX_IMMUTABLE',
    'CAP_NET_BIND_SERVICE','CAP_NET_BROADCAST','CAP_NET_ADMIN','CAP_NET_RAW','CAP_IPC_LOCK',
    'CAP_IPC_OWNER','CAP_SYS_MODULE','CAP_SYS_RAWIO','CAP_SYS_CHROOT','CAP_SYS_PTRACE',
    'CAP_SYS_PACCT','CAP_SYS_ADMIN','CAP_SYS_BOOT','CAP_SYS_NICE','CAP_SYS_RESOURCE',
    'CAP_SYS_TIME','CAP_SYS_TTY_CONFIG','CAP_MKNOD','CAP_LEASE','CAP_AUDIT_WRITE',
    'CAP_AUDIT_CONTROL','CAP_SETFCAP','CAP_MAC_OVERRIDE','CAP_MAC_ADMIN','CAP_SYSLOG',
    'CAP_WAKE_ALARM','CAP_BLOCK_SUSPEND','CAP_AUDIT_READ'
]


def read_file(p):
    if not p or not os.path.exists(p):
        return ""
    with open(p, 'r', encoding='utf-8', errors='ignore') as fh:
        return fh.read()


def suggest_from_runtime(runtime_text, stderr_text):
    suggestions = []
    notes = []

    if not runtime_text:
        notes.append('runtime_info.txt empty or missing')
        # suggest common syscalls for python if no info
        suggestions.extend(CANDIDATE_SYSCALLS[:3])
        return suggestions, notes

    # Check for Seccomp field
    m = RE_SEC_COMP.search(runtime_text)
    if m:
        sec = int(m.group(1))
        notes.append(f'Seccomp field detected: {sec}')
        if sec == 0:
            notes.append('Seccomp disabled in container')
        else:
            notes.append('Seccomp appears enabled')
    else:
        notes.append('No Seccomp field found')

    # Look for common Python misfires in stderr
    if stderr_text:
        if 'Operation not permitted' in stderr_text or 'seccomp' in stderr_text.lower():
            notes.append('Detected permission/seccomp errors in stderr')
            suggestions.extend(CANDIDATE_SYSCALLS[:4])

    # Heuristic: if runtime text mentions a denied syscall (some distributions log it)
    denied = []
    for line in runtime_text.splitlines():
        if 'denied' in line.lower() or 'syscall' in line.lower():
            denied.append(line.strip())
    if denied:
        notes.append('Found lines mentioning denied syscalls or errors')
        # include the last token words as possible syscall names
        for d in denied:
            parts = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]+", d)
            for p in parts[-3:]:
                if p not in suggestions:
                    suggestions.append(p)

    # Fall back to a few safe candidates if suggestions empty
    if not suggestions:
        suggestions.extend(CANDIDATE_SYSCALLS[:2])

    # parse CapEff if present and include capability names
    caps_found = []
    m2 = RE_CAPEFF.search(runtime_text)
    if m2:
        try:
            hexval = m2.group(1)
            # normalize like 0x... or hex digits
            hexval = hexval.lower().replace('0x','')
            bitmask = int(hexval, 16)
            for i, name in enumerate(CAPABILITY_NAMES):
                if bitmask & (1 << i):
                    caps_found.append(name)
            if caps_found:
                notes.append('Capabilities present: ' + ','.join(caps_found))
        except Exception:
            pass

    return suggestions, notes


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--runtime', default='runtime_info.txt')
    p.add_argument('--stderr', default='runtime_error.txt')
    p.add_argument('--out', default='diagnostics')
    args = p.parse_args()

    runtime = read_file(args.runtime)
    stderr = read_file(args.stderr)

    suggestions, notes = suggest_from_runtime(runtime, stderr)

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, 'suggestion.json'), 'w', encoding='utf-8') as fh:
        json.dump({'suggestions': suggestions, 'notes': notes}, fh, indent=2)
    with open(os.path.join(args.out, 'diagnostics.txt'), 'w', encoding='utf-8') as fh:
        fh.write('---RUNTIME---\n')
        fh.write(runtime or '(empty)')
        fh.write('\n---STDERR---\n')
        fh.write(stderr or '(empty)')
        fh.write('\n---NOTES---\n')
        for n in notes:
            fh.write(n + '\n')

    print('Wrote diagnostics to', args.out)
