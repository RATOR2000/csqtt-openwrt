#!/usr/bin/env python3
"""Boot a disposable pinned stock OpenWrt VM and exercise the signed installer.

Only loopback host forwarding and a new temporary disk/key are used. No physical
router connection is supported. The provisionally qualified fixture is private
to this test; release qualification is generated only after this command passes.
"""
import argparse
import functools
import hashlib
import http.server
import importlib.util
import json
import os
import pathlib
import re
import shlex
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error

from release_schema import describe, load, require, validate
from openwrt_image import extract_openwrt_image
from vm_disk import expand_disposable_root
from vm_console import prepare_guest_console
from vm_timeout import build_timeout, provision_timeout

ROOT = pathlib.Path(__file__).resolve().parents[1]
IMAGES = {
    '25.12.5': '23e2538e8ab0eb52dfed1c65d608ecdb71ffd432dd54885da138ae67cd9e4461',
    '24.10.8': '23872c64fdb66d0765e0d17f71453a66e7a91e9ecb10606d5f738e6d166e14ae',
    '25.12.6': 'f8538784d0288b4133a99ac2a68443e4922ffde6343e80df56a5882364b9d499',
}
PHASE = 'host_preflight'
SIGNATURE_REJECTION = 'CSQTT: Подпись выпуска недействительна'
DIAGNOSTIC_READ_OK = 'CSQTT_PRIVATE_LOG_READ_OK'
DIAGNOSTIC_LIMIT = 8192
DIAGNOSTIC_SCAN_LIMIT = 1024 * 1024
BOOTSTRAP_SOLVER_ERROR = 'CSQTT: Средства проверки недоступны без изменения системных пакетов'
BOOTSTRAP_PACKAGES = ('openssl-util', 'jsonfilter')
PROJECT_STAGE_ERROR = 'CSQTT: Проверка автономной установки в изолированной базе завершилась ошибкой'
PROJECT_STAGE_PACKAGES = ('csqtt', 'csqtt-captcha', 'luci-app-csqtt') + BOOTSTRAP_PACKAGES
OPKG_SOLVER_ERRORS = {
    'unknown_package': ('Unknown package ',),
    'cannot_install': ('opkg_install_cmd: Cannot install package ',),
    'dependency_unsatisfied': ('cannot find dependency ', 'Cannot satisfy the following dependencies'),
    'architecture_mismatch': ('incompatible with the architectures configured',),
    'download_failed': ('Failed to download ',),
    'signature_rejected': ('Signature check failed', 'Signature verification failed'),
    'file_read': ('Could not open ', 'Failed to open ', 'No such file or directory'),
    'file_conflict': ('check_data_file_clashes:', 'already provided by package'),
    'resource_limit': ('No space left on device',),
}
APK_SOLVER_ERRORS = {
    'permission_denied': ('Permission denied', 'Operation not permitted'),
    'read_only_filesystem': ('Read-only file system',),
    'io_error': ('I/O error', 'IO ERROR'),
    'invalid_argument': ('Invalid argument',),
    # Literal templates from the pinned official target apk; values stay private.
    'database_open': ('Failed to open apk database:', 'Unable to read database', 'Unable to open root:'),
    'database_lock': ('Unable to lock database', 'Refusing to write db without write lock!'),
    'cache_setup': ('Unable to setup the cache', 'Unable to open log:'),
    'package_extract': ('failed to extract ', 'failed to commit ', 'unable to cache package'),
    'repository_format': ('repositories file syntax error', 'package mentioned in index not found',
                          'could not find a repo which provides this package'),
    'unsupported_format': ('file format is invalid or inconsistent', 'file format not supported (in this applet)',
                           'v2 database format error'),
    'integrity_error': ('ADB integrity error',),
    'unsupported_root': ('uvol not supported with --root',),
    'option_argument': ('invalid argument for option', "setting option '"),
    'usage_output': ('Usage: apk ', 'usage: apk '),
    'unsupported_option': ('unrecognized option', 'unrecognized command line option', 'unknown option', 'invalid option'),
    'unknown_package': ('(no such package)',),
    'dependency_unsatisfied': ('unable to select packages:',),
    'version_conflict': ('breaks:', 'conflicts:'),
    'architecture_mismatch': ('BAD architecture', 'unsupported architecture'),
    'signature_rejected': ('UNTRUSTED signature', 'BAD signature', 'UNTRUSTED public key'),
    'index_rejected': ('BAD archive', 'BAD index', 'UNTRUSTED index', 'UNTRUSTED packages'),
    'world_constraint': ('world[',),
    'file_read': ('No such file or directory', 'could not open'),
    'file_conflict': ('trying to overwrite ',),
    'resource_limit': ('No space left on device',),
    'checksum_mismatch': ('BAD checksum', 'checksum mismatch'),
}
PRIVATE_TRACE = "PS4='+CSQTT_XTRACE:${LINENO:-0}: '; export PS4; sh -x install.sh ci-private"
GUEST_PRIVATE_TRACE = "PS4='+CSQTT_GUEST_TRACE:${LINENO:-0}: '; export PS4; sh -x guest.sh"
KNOWN_TOOLS = ('uclient-fetch', 'sha256sum', 'awk', 'tar', 'sync', 'du', 'mktemp', 'wc', 'sed', 'cut',
               'cat', 'cp', 'mkdir', 'rm', 'mv', 'rmdir', 'chmod', 'grep', 'sort', 'tr', 'date', 'sleep',
               'id', 'openssl', 'jsonfilter', 'usign', 'opkg', 'apk', 'uci', 'ubus', 'dd', 'tail')
SHELL_ERRORS = {
    'syntax_error': ('syntax error',),
    'unset_parameter': ('parameter not set', 'unbound variable'),
    'arithmetic_error': ('arithmetic syntax error', 'arithmetic expression'),
    'permission_denied': ('Permission denied',),
    'read_only_filesystem': ('Read-only file system',),
}
PRIVATE_PHASE_LOGS = {
    'bootstrap_and_signature_rejection': 'reject',
    'first_offline_install': 'install',
    'native_runtime_dns_firewall_luci': 'smoke',
    'repeat_install_settings_preserved': 'repeat',
}


def phase(value):
    global PHASE
    PHASE = value
    print('OpenWrt VM phase: ' + value, flush=True)


def failure_message(error):
    # Exception messages, commands, URLs, output and filenames may contain
    # private data. Emit only its class and a bounded numeric HTTP status.
    category = type(error).__name__
    category = category if re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,79}', category) else 'Exception'
    status = ''
    if isinstance(error, urllib.error.HTTPError) and type(error.code) is int and 100 <= error.code <= 599:
        status = ' http_status=' + str(error.code)
    return ('Clean OpenWrt VM acceptance failed at stage=' + PHASE + ' exception=' + category + status +
            '; private diagnostics are not printed or published.')


def free_port():
    with socket.socket() as bound:
        bound.bind(('127.0.0.1', 0))
        return bound.getsockname()[1]


def installer_diagnostics(private):
    """Map bounded private text to trusted source line numbers and fixed enums."""
    private = private[-40960:]
    source = (ROOT / 'scripts/portable-install.sh').read_text(encoding='utf-8')
    errors = set()
    for number, line in enumerate(source.splitlines(), 1):
        for match in re.finditer(r"\bcsqtt_portable_die\s+'([^'\r\n]+)'", line):
            # Only complete hardcoded messages qualify, never a dynamic value
            # or a matching prefix taken from configuration/package output.
            if re.search(r'(?m)^CSQTT: ' + re.escape(match[1]) + r'\r?$', private):
                errors.add(number)
    tools = []
    for tool in KNOWN_TOOLS:
        explicit = 'CSQTT: В прошивке отсутствует необходимая команда: ' + tool
        missing = r'(?m)(?:^|[ :])' + re.escape(tool) + r': (?:not found|command not found)\r?$'
        if re.search(r'(?m)^' + re.escape(explicit) + r'\r?$', private) or re.search(missing, private):
            tools.append(tool)
    shell = [name for name, needles in SHELL_ERRORS.items() if any(needle in private for needle in needles)]
    generated_lines = sorted({int(n) for n in re.findall(
        r'(?m)^(?:install\.sh|[^ \r\n]*/install\.sh): (?:line )?([1-9][0-9]{0,4}):', private)
        if int(n) <= len((ROOT / 'install.sh').read_text(encoding='utf-8').splitlines())})
    installer = (ROOT / 'install.sh').read_text(encoding='utf-8').splitlines()
    functions = set(re.findall(r'^(csqtt_[A-Za-z0-9_]+)\(\)', '\n'.join(installer), re.MULTILINE))
    traced_functions, last_line = [], None
    for line in private.splitlines():
        trace = re.match(r'^\++CSQTT_XTRACE:([0-9]{1,6}):\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s|$)', line)
        if not trace:
            continue
        number, name = int(trace[1]), trace[2]
        # Stop before EXIT cleanup obscures the original failure. The emitted
        # names and source numbers are defined by this checkout, never values.
        if name in ('csqtt_portable_cleanup', 'csqtt_operation_cleanup'):
            break
        if 0 < number <= len(installer):
            last_line = number
        if name in functions and (not traced_functions or traced_functions[-1] != name):
            traced_functions.append(name)
    return {'portable_error_lines': sorted(errors), 'missing_tools': tools, 'shell_errors': shell,
            'generated_error_lines': generated_lines, 'trace_functions': traced_functions[-8:],
            'trace_last_source_line': last_line, 'platform_trace': platform_trace_diagnostics(private, installer)}


def platform_trace_diagnostics(private, installer):
    """Classify probe assignments at their exact source lines, never print values."""
    fields = {'CS_PROFILE': 'profile_id', 'CS_ARCH': 'architecture',
              'CS_FAMILY': 'family', 'CS_PM': 'package_manager'}
    locations = {}
    for name, field in fields.items():
        assignment = name + '=$(csqtt_j "$CS_TMP/probe.json" \'@.' + field + '\')'
        matches = [number for number, line in enumerate(installer, 1) if assignment in line]
        if len(matches) == 1:
            locations[name] = matches[0]
    result = {name: 'unobserved' for name in fields}
    for line in private.splitlines():
        trace = re.fullmatch(r'\++CSQTT_XTRACE:([0-9]{1,6}):\s+(.*)', line)
        if not trace:
            continue
        number, command = int(trace[1]), trace[2]
        if re.match(r'(?:csqtt_portable_cleanup|csqtt_operation_cleanup)(?:\s|$)', command):
            break
        # shlex decodes shell trace quoting without evaluating any command text.
        # Only assignment-only commands at a unique source-known probe line count.
        try:
            words = shlex.split(command)
        except ValueError:
            continue
        if not words or any(not re.match(r'^CS_[A-Z_]+=', word) for word in words):
            continue
        for word in words:
            name, value = word.split('=', 1)
            if locations.get(name) != number:
                continue
            if not value:
                category = 'blank'
            elif name in ('CS_PROFILE', 'CS_ARCH'):
                category = 'valid' if (len(value) <= 200 and not value.startswith(('.', '-')) and
                                      re.fullmatch(r'[A-Za-z0-9_.+~-]+', value)) else 'invalid'
            else:
                allowed = ('official',) if name == 'CS_FAMILY' else ('apk', 'opkg')
                category = value if value in allowed else 'unrecognized'
            result[name] = category
    return result


def _private_log_size():
    return ('n=$(wc -c < "$f") || exit 1; set -- $n; [ "$#" = 1 ] || exit 1; n=$1; '
            'case "$n" in ""|*[!0-9]*) exit 1;; esac; ')


def _private_log_tail():
    # Baseline BusyBox wc/dd suffice; tail -c is not a required capability.
    # The byte count and read must both succeed before the sentinel is emitted.
    # No earlier phase log may supply a reason for the current failure.
    return ('[ -f "$f" ] && [ ! -L "$f" ] || exit 1; ' + _private_log_size() +
            'skip=0; [ "$n" -le 8192 ] || skip=$((n-8192)); '
            'dd if="$f" bs=1 skip="$skip" count=8192 2>/dev/null || exit 1; '
            'printf "\\n' + DIAGNOSTIC_READ_OK + '\\n"')


def private_log_read_command():
    name = PRIVATE_PHASE_LOGS.get(PHASE)
    return 'exit 1' if name is None else 'f=/tmp/csqtt-native/' + name + '.private.log; ' + _private_log_tail()


def bootstrap_solver_read_command():
    """Discover one exact traced temporary root; read only its fixed solver log."""
    return _nested_log_read_command('bootstrap/solver.log')


def project_stage_read_command(native_head=False):
    if PHASE not in ('first_offline_install', 'repeat_install_settings_preserved'):
        return 'exit 1'
    source = (ROOT / 'scripts/portable-install.sh').read_text(encoding='utf-8')
    known = ('csqtt_pm_install "$CS_TMP/stage" "$CS_TMP" 0 > "$CS_TMP/stage.log" 2>&1 || csqtt_portable_die \'' +
             PROJECT_STAGE_ERROR.removeprefix('CSQTT: ') + '\'')
    if source.count(known) != 1:
        return 'exit 1'
    return _nested_log_read_command('stage.log', native_head=native_head)


def _private_native_output_head():
    # The package-manager's error can precede a long usage listing. Select only
    # its first bounded output after the unique, source-known staged APK call.
    command = ('apk --root "$CS_PM_ROOT" --arch "$CS_ARCH" --repositories-file "$CS_REPOSITORIES" '
               '--keys-dir etc/apk/keys --no-network --no-scripts --force-non-repository add "$@"')
    lines = [n for n, line in enumerate((ROOT / 'install.sh').read_text(encoding='utf-8').splitlines(), 1)
             if line.strip() == command]
    if len(lines) != 1:
        return 'exit 1'
    marker = '^[+]+CSQTT_XTRACE:' + str(lines[0]) + ': apk '
    program = ('{total+=length($0)+1;if(total>' + str(DIAGNOSTIC_SCAN_LIMIT) + '){bad=1;exit} '
               'if($0 ~ "' + marker + '"){matches++;active=1;next} '
               'if(active && $0 ~ "^[+]+CSQTT_XTRACE:")active=0; '
               'if(active && bytes<' + str(DIAGNOSTIC_LIMIT) + '){part=substr($0 "\\n",1,' +
               str(DIAGNOSTIC_LIMIT) + '-bytes);body=body part;bytes+=length(part)}} '
               'END{if(bad || matches!=1)exit 1;printf "%s",body}')
    return ('[ -f "$f" ] && [ ! -L "$f" ] || exit 1; ' + _private_log_size() +
            '[ "$n" -le ' + str(DIAGNOSTIC_SCAN_LIMIT) + ' ] || exit 1; '
            'LC_ALL=C awk \'' + program + '\' "$f" || exit 1; '
            'printf "\\n' + DIAGNOSTIC_READ_OK + '\\n"')


def _nested_log_read_command(relative, native_head=False):
    if relative not in ('bootstrap/solver.log', 'stage.log') or native_head and relative != 'stage.log':
        return 'exit 1'
    name = PRIVATE_PHASE_LOGS.get(PHASE)
    assignments = [number for number, line in enumerate((ROOT / 'install.sh').read_text(encoding='utf-8').splitlines(), 1)
                   if line.strip() == 'CS_TMP=$(mktemp -d /tmp/csqtt-portable.XXXXXX)']
    if name is None or len(assignments) != 1:
        return 'exit 1'
    traced = '^[+]+CSQTT_XTRACE:' + str(assignments[0]) + ': CS_TMP='
    path_pattern = '^/tmp/csqtt-portable[.]' + '[A-Za-z0-9]' * 6 + '$'
    # Read no package-selected path and never evaluate trace text as shell code.
    # Discovery scans only a bounded completed phase log; it prints no log text.
    program = ('{line=$0; sub(/\\r$/,"",line); total+=length(line)+1; '
               'if(total>' + str(DIAGNOSTIC_SCAN_LIMIT) + '){bad=1;exit} '
               'if(line ~ "' + traced + '"){count++;sub("' + traced + '","",line); '
               'if(line !~ "' + path_pattern + '")bad=1;root=line}} '
               'END{if(count!=1 || bad)exit 1;print root}')
    child_guard = ('[ -d "$d/bootstrap" ] && [ ! -L "$d/bootstrap" ] || exit 1; '
                   if relative == 'bootstrap/solver.log' else '')
    return ('[ -d /tmp ] && [ ! -L /tmp ] && [ -d /tmp/csqtt-native ] && '
            '[ ! -L /tmp/csqtt-native ] || exit 1; '
            'f=/tmp/csqtt-native/' + name + '.private.log; [ -f "$f" ] && [ ! -L "$f" ] || exit 1; ' +
            _private_log_size() + '[ "$n" -le ' + str(DIAGNOSTIC_SCAN_LIMIT) + ' ] || exit 1; '
            'd=$(awk \'' + program + '\' "$f") || exit 1; '
            '[ -d "$d" ] && [ ! -L "$d" ] || exit 1; ' + child_guard +
            'f="$d/' + relative + '"; ' + (_private_native_output_head() if native_head else _private_log_tail()))


def read_private_diagnostic(ssh, command):
    try:
        result = subprocess.run(ssh + [command], capture_output=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    sentinel = ('\n' + DIAGNOSTIC_READ_OK + '\n').encode('ascii')
    if (result.returncode != 0 or not result.stdout.endswith(sentinel) or
            len(result.stdout) > DIAGNOSTIC_LIMIT + len(sentinel)):
        return None
    # Check the original byte bound before decoding a possibly partial UTF-8 tail.
    return result.stdout[:-len(sentinel)].decode('utf-8', errors='replace')


def bootstrap_solver_diagnostics(private):
    """Expose fixed opkg classes and only requested, source-known package names."""
    private = private[-DIAGNOSTIC_LIMIT:]
    classes = [name for name, needles in OPKG_SOLVER_ERRORS.items() if any(needle in private for needle in needles)]
    packages = [name for name in BOOTSTRAP_PACKAGES if re.search(
        r'(?<![A-Za-z0-9_.+~-])' + re.escape(name) + r'(?=$|[^A-Za-z0-9_.+~-]|[.]\r?$)', private, re.MULTILINE)]
    return {'classes': classes or ['unclassified_output' if private else 'empty_output'], 'packages': packages}


def project_stage_diagnostics(private):
    """Emit only fixed native solver classes and source-known project/tool names."""
    private = private[-DIAGNOSTIC_LIMIT:]
    classes = sorted({name for errors in (OPKG_SOLVER_ERRORS, APK_SOLVER_ERRORS)
                      for name, needles in errors.items() if any(needle in private for needle in needles)})
    packages = [name for name in PROJECT_STAGE_PACKAGES if re.search(
        r'(?<![A-Za-z0-9_.+~-])' + re.escape(name) + r'(?=$|[^A-Za-z0-9_.+~-]|[.]\r?$)', private, re.MULTILINE)]
    return {'classes': classes or ['unclassified_output' if private else 'empty_output'], 'packages': packages}


def first_install_native_errors(text):
    """Redact APK errors only: clean firmware DB/public packages, no scripts.

    The caller is restricted to the first disposable installation, before any
    runtime/identity or user settings exist. Never expose shell traces or files.
    """
    result = []
    for line in text[:DIAGNOSTIC_LIMIT].splitlines():
        line = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', line).lstrip()
        if not re.match(r'^(?:ERROR|WARNING|apk):', line, re.IGNORECASE):
            continue
        line = re.sub(r'[A-Za-z][A-Za-z0-9+.-]*://\S+', '<url>', line)
        line = re.sub(r'(?i)\b(password|secret|token|grant|identity|key)\s*[=:]\s*(?:\'[^\']*\'|"[^"]*"|\S+)', r'\1=<redacted>', line)
        line = re.sub(r'(?:/[^\s\'"<>:;()]+)+', '<path>', line)
        line = re.sub(r'[A-Za-z0-9_+=/-]{32,}', '<value>', line)
        line = ''.join(character for character in line if character.isprintable())
        result.append(line[:300])
        if len(result) == 6:
            break
    return result


def guest_ucode_diagnostics(private, source=ROOT):
    """Accept fixed ucode classes and locations within the exact public sources."""
    classes = sorted(set(re.findall(r'(?m)^CSQTT_GUEST_UCODE_CLASS=(syntax_error|reference_error|type_error|module_error)\r?$', private)))
    locations = set()
    for filename, value in re.findall(r'(?m)^CSQTT_GUEST_UCODE_SOURCE=(runtime[.]uc|policy[.]uc|health[.]uc):([1-9][0-9]{0,5})\r?$', private):
        path = source / 'openwrt/csqtt/files' / filename
        if path.is_file() and int(value) <= len(path.read_text(encoding='utf-8').splitlines()):
            locations.add((filename, int(value)))
    return {'classes': classes, 'locations': sorted(locations)[:8]}


def guest_web_diagnostics(private):
    """Only fixed disposable-guest web states; never HTML, headers or log text."""
    private = private[-DIAGNOSTIC_LIMIT:]
    def values(marker, pattern):
        return sorted(set(re.findall(r'(?m)^CSQTT_GUEST_WEB_' + marker + '=' + pattern + r'\r?$', private)))
    codes = lambda marker: [int(n) for n in values(marker, r'([0-9]{1,3})') if int(n) <= 255]
    return {
        'exit': codes('EXIT'), 'service_exit': codes('SERVICE_EXIT'), 'cgi_exit': codes('CGI_EXIT'),
        'read_exit': codes('READ_EXIT'),
        'bytes': [int(n) for n in values('BYTES', r'([0-9]{1,6})') if int(n) <= 131073],
        'parse': values('PARSE', r'(header_format|status_line|auth_header|content_type|body_size|content_length|'
                       r'transfer_encoding|html_document|login_form|username_input|password_input|password_type)'),
        'status': [int(n) for n in values('STATUS', r'([1-5][0-9][0-9])')],
        'checks': values('CHECK', r'(uhttpd_running|uhttpd_stopped|port80_listening|port80_closed|'
                         r'port443_listening|port443_closed|cgi_executable|cgi_not_executable|'
                         r'uhttpd_ucode_present|uhttpd_ucode_missing|root_http_ok|root_http_failed)'),
        'files': values('FILE', r'((?:cgi|dispatcher|runtime|template|http):(?:present|missing))'),
        'modules': values('MODULE', r'((?:fs|ubus|uci|uloop|math|html):(?:loaded|failed))'),
        'classes': values('CLASS', r'(connection_refused|timeout|permission_denied|cgi_execute|cgi_gateway|option_unsupported|tls_certificate|tls_hostname|tls_unavailable|local_https_redirect|'
                          r'syntax_error|reference_error|type_error|runtime_error|module_error)'),
        'locations': [(name, int(number)) for name, number in values('SOURCE',
                      r'((?:luci[.](?:cgi|dispatcher|runtime|template|http)|csqtt[.](?:runtime|policy|health))):([1-9][0-9]{0,4})')
                      if int(number) <= 20000][:8],
    }


def print_guest_web_diagnostics(private, prefix):
    for field, values in guest_web_diagnostics(private).items():
        for value in values:
            if isinstance(value, tuple):
                value = value[0] + ':' + str(value[1])
            print(prefix + ' web ' + field + ': ' + str(value), flush=True)


def guest_trace_diagnostics(private, source=None):
    """Expose only an owned assertion call line, before fail/cleanup internals."""
    if source is None:
        source = ROOT / 'scripts/test-openwrt-guest.sh'
    lines = source.read_text(encoding='utf-8').splitlines()
    definitions = {number for number, line in enumerate(lines, 1)
                   if re.match(r'^\s*fail\(\)', line)}
    assertions = {number for number, line in enumerate(lines, 1)
                  if number not in definitions and not line.lstrip().startswith('#') and
                  re.search(r'(?:^|[;&|)\s])fail(?:[;\s]|$)', line)}
    for number, command in re.findall(r'(?m)^\+CSQTT_GUEST_TRACE:([0-9]{1,6}): ([^\r\n]*)\r?$',
                                      private[-DIAGNOSTIC_LIMIT:]):
        number = int(number)
        if number in definitions or re.match(r'^cleanup(?:\s|$)', command):
            break
        if number in assertions and command.strip() == 'fail':
            return number
    return None


def guest_trace_metadata(private):
    """Keep fixed command names when a firmware shell lacks assertion LINENO."""
    commands = {'ucode': 'ucode', 'jsonfilter': 'jsonfilter', 'grep': 'grep',
                '/usr/libexec/csqtt/manage': 'manage', '/usr/libexec/rpcd/csqtt': 'rpc',
                'timeout': 'timeout', '[': 'test', 'cat': 'cat'}
    result = {'format': 'missing', 'command': 'unknown', 'source_line': None}
    size = len((ROOT / 'scripts/test-openwrt-guest.sh').read_text(encoding='utf-8').splitlines())
    for line in private[-DIAGNOSTIC_LIMIT:].splitlines():
        owned = re.fullmatch(r'\++CSQTT_GUEST_TRACE:([0-9]{1,6}):\s*(.*)', line)
        fallback = re.fullmatch(r'\+\s+(.*)', line) if not owned else None
        if not owned and not fallback:
            continue
        command = owned[2] if owned else fallback[1]
        try:
            words = shlex.split(command)
        except ValueError:
            continue
        if not words:
            continue
        if words[0] in ('fail', 'cleanup'):
            break
        if words[0] in commands:
            result['format'] = 'owned' if owned else 'default'
            result['command'] = commands[words[0]]
            number = int(owned[1]) if owned else 0
            result['source_line'] = number if 0 < number <= size else None
    return result


def guest_smoke_command(directory):
    """Tracing follows PASS with an exit trace, so verify the complete PASS line."""
    require(directory in ('/tmp/csqtt-native', '/tmp/csqtt-public'), 'Unknown disposable guest directory')
    return ('cd ' + directory + '; ' + GUEST_PRIVATE_TRACE +
            ' > smoke.private.log 2>&1 && grep -Fqx CSQTT_GUEST_SMOKE_PASS smoke.private.log && '
            "printf '%s\\n' CSQTT_GUEST_SMOKE_PASS")


def run_remote(ssh, command, timeout=600, check=True):
    result = subprocess.run(ssh + ['set -eu; ' + command], capture_output=True, text=True, timeout=timeout)
    # Private native diagnostics never enter public evidence/logs.
    if check and result.returncode:
        print(f'OpenWrt VM failure: stage={PHASE} exit={result.returncode}', flush=True)
        # Capture only bounded private diagnostics into host memory;
        # emit fixed enums, never package logs or configuration text.
        log = read_private_diagnostic(ssh, private_log_read_command())
        if log is None:
            print('OpenWrt guest diagnostics: diagnostic_unavailable', flush=True)
            private = result.stderr[-DIAGNOSTIC_LIMIT:]
        else:
            print('OpenWrt guest diagnostics: bounded_read_ok', flush=True)
            private = (log + result.stderr[-DIAGNOSTIC_LIMIT:])[-DIAGNOSTIC_LIMIT:]
        classified = installer_diagnostics(private)
        for line in classified['portable_error_lines']:
            print('OpenWrt installer error: portable_source_line=' + str(line), flush=True)
        for line in classified['generated_error_lines']:
            print('OpenWrt installer shell location: generated_line=' + str(line), flush=True)
        for tool in classified['missing_tools']:
            print('OpenWrt missing tool: ' + tool, flush=True)
        for category in classified['shell_errors']:
            print('OpenWrt shell error: ' + category, flush=True)
        for name in classified['trace_functions']:
            print('OpenWrt installer trace function: ' + name, flush=True)
        if classified['trace_last_source_line'] is not None:
            print('OpenWrt installer trace: generated_source_line=' + str(classified['trace_last_source_line']), flush=True)
        for name, category in classified['platform_trace'].items():
            if category != 'unobserved':
                print('OpenWrt installer platform trace: ' + name + '=' + category, flush=True)
        guest_source = (ROOT / 'scripts/test-openwrt-guest.sh').read_text(encoding='utf-8')
        allowed_stages = set(re.findall(r'^stage ([a-z_]{1,50})$', guest_source, re.MULTILINE))
        markers = [m for m in re.findall(r'CSQTT_GUEST_STAGE=([a-z_]{1,50})(?:\s|$)', private) if m in allowed_stages]
        if markers:
            print('OpenWrt guest substage: ' + markers[-1], flush=True)
        if PHASE == 'native_runtime_dns_firewall_luci':
            assertion = guest_trace_diagnostics(private)
            print('OpenWrt guest assertion: ' + ('source_line=' + str(assertion) if assertion is not None else
                  'unknown'), flush=True)
            trace = guest_trace_metadata(private)
            print('OpenWrt guest trace format: ' + trace['format'], flush=True)
            print('OpenWrt guest trace command: ' + trace['command'], flush=True)
            if trace['source_line'] is not None:
                print('OpenWrt guest trace source_line=' + str(trace['source_line']), flush=True)
            ucode = guest_ucode_diagnostics(private)
            for category in ucode['classes']:
                print('OpenWrt guest ucode class: ' + category, flush=True)
            for filename, number in ucode['locations']:
                print('OpenWrt guest ucode source: ' + filename + ':' + str(number), flush=True)
            print_guest_web_diagnostics(private, 'OpenWrt guest')
        guest_tools = {tool for group in re.findall(r'^for tool in ([a-z0-9 _-]+); do command -v "\$tool"',
                                                    guest_source, re.MULTILINE) for tool in group.split()}
        for tool in sorted(set(re.findall(r'(?m)^CSQTT_GUEST_MISSING_TOOL=([a-z0-9_-]{1,50})\r?$', private)) & guest_tools):
            print('OpenWrt guest missing tool: ' + tool, flush=True)
        reasons = {
            'signature_rejected': ('UNTRUSTED signature', 'BAD signature', 'Verification failure', 'подпись'),
            'dependency_solver': ('unable to select packages', 'unsatisfiable', 'Неполный набор зависимостей', 'не прошла в изолированной базе'),
            'resource_limit': ('Недостаточно', 'No space left'),
            'network_fetch': ('Connection failed', 'Failed to download', 'не удалось скачать', 'Не удалось скачать'),
            'kernel_abi': ('ядра не совпадает', 'kernel mismatch'),
        }
        for reason, needles in reasons.items():
            if any(needle in private for needle in needles):
                print('OpenWrt guest reason: ' + reason, flush=True)
        if log is not None and re.search(r'(?m)^' + re.escape(BOOTSTRAP_SOLVER_ERROR) + r'\r?$', log):
            nested = read_private_diagnostic(ssh, bootstrap_solver_read_command())
            if nested is None:
                print('OpenWrt bootstrap solver diagnostics: diagnostic_unavailable', flush=True)
            else:
                print('OpenWrt bootstrap solver diagnostics: bounded_read_ok', flush=True)
                solver = bootstrap_solver_diagnostics(nested)
                for category in solver['classes']:
                    print('OpenWrt bootstrap solver class: ' + category, flush=True)
                for package in solver['packages']:
                    print('OpenWrt bootstrap solver package: ' + package, flush=True)
        if (log is not None and PHASE in ('first_offline_install', 'repeat_install_settings_preserved') and
                re.search(r'(?m)^' + re.escape(PROJECT_STAGE_ERROR) + r'\r?$', log)):
            nested = read_private_diagnostic(ssh, project_stage_read_command())
            if nested is None:
                print('OpenWrt project stage diagnostics: diagnostic_unavailable', flush=True)
            else:
                print('OpenWrt project stage diagnostics: bounded_read_ok', flush=True)
                solver = project_stage_diagnostics(nested)
                for category in solver['classes']:
                    print('OpenWrt project stage class: ' + category, flush=True)
                for package in solver['packages']:
                    print('OpenWrt project stage package: ' + package, flush=True)
                if set(solver['classes']) <= {'unclassified_output', 'usage_output'}:
                    native = read_private_diagnostic(ssh, project_stage_read_command(native_head=True))
                    print('OpenWrt project native output: ' + ('bounded_read_ok' if native is not None else
                          'diagnostic_unavailable'), flush=True)
                    if native is not None:
                        for category in project_stage_diagnostics(native)['classes']:
                            print('OpenWrt project native output class: ' + category, flush=True)
                        if PHASE == 'first_offline_install':
                            for error in first_install_native_errors(native):
                                print('OpenWrt first-install APK error: ' + error, flush=True)
                traced = installer_diagnostics(nested)
                for name in traced['trace_functions']:
                    print('OpenWrt project stage trace function: ' + name, flush=True)
                if traced['trace_last_source_line'] is not None:
                    print('OpenWrt project stage trace: generated_source_line=' + str(traced['trace_last_source_line']), flush=True)
                for category in traced['shell_errors']:
                    print('OpenWrt project stage shell error: ' + category, flush=True)
                for tool in traced['missing_tools']:
                    print('OpenWrt project stage missing tool: ' + tool, flush=True)
        raise ValueError('Disposable guest command failed; native acceptance was not granted')
    return result


def require_signature_rejection(remote, rejected):
    require(rejected.returncode != 0, 'Wrong project signature was accepted')
    # A missing tool or other early refusal cannot count as signature evidence.
    remote("cd /tmp/csqtt-native; grep -Fqx '" + SIGNATURE_REJECTION +
           "' reject.private.log; sha256sum -c before.sha256 >/dev/null; test ! -x /usr/bin/csqtt-client")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=pathlib.Path, required=True)
    parser.add_argument('--profile', required=True)
    args = parser.parse_args()
    phase('validation')
    manifest = validate(load(args.directory / (args.profile + '-manifest.json')), args.directory)
    platform = manifest['platform']
    require(platform['target'] == 'x86/64' and platform['architecture'] == 'x86_64', 'VM guest must use its own exact x86 package/kernel tuple')
    version = platform['openwrt']
    require(version in IMAGES, 'No pinned clean firmware image')
    require(manifest['qualification'].get('reason') == 'private_ci_fixture_only', 'Use an isolated signed provisional fixture')
    phase('imports')
    import pexpect  # CI installs this small host-only console driver.
    spec = importlib.util.spec_from_file_location('bundle', ROOT / 'scripts/bundle-dependencies.py')
    bundle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bundle)
    evidence_spec = importlib.util.spec_from_file_location('evidence', ROOT / 'scripts/release-evidence.py')
    evidence = importlib.util.module_from_spec(evidence_spec)
    evidence_spec.loader.exec_module(evidence)
    output = args.directory / (args.profile + '-vm-evidence.json')
    phase('fixture_copy')
    with tempfile.TemporaryDirectory(prefix='csqtt-vm-') as temporary:
        work = pathlib.Path(temporary)
        phase('test_timeout_build')
        test_timeout = build_timeout(work)
        web = work / 'web'
        web.mkdir()
        fixture = web / 'ci-private'
        shutil.copytree(args.directory, fixture)
        catalogue = {'schema': 2, 'upstream': manifest['upstream'], 'profiles': [{
            **describe(fixture / (args.profile + '-manifest.json')), 'profile_id': args.profile,
            'signature': describe(fixture / (args.profile + '-manifest.sig'))}]}
        (fixture / 'catalogue.json').write_text(json.dumps(catalogue, indent=2) + '\n')
        # sign-portable-release refuses a provisional catalogue by design. Sign
        # only this test's exact private catalogue with a short-lived key file.
        phase('catalogue_signing')
        secret = os.environ.pop('CSQTT_SIGNING_KEY', '')
        require(secret, 'Private CI fixture signing key unavailable')
        key = work / 'fixture-signing.pem'
        key.write_text(secret)
        key.chmod(0o600)
        secret = None
        subprocess.run(['openssl', 'dgst', '-sha256', '-sign', str(key), '-out', str(fixture / 'catalogue.sig'),
                        str(fixture / 'catalogue.json')], check=True, capture_output=True)
        key.unlink()
        phase('fixture_server')
        class QuietHandler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *unused):
                pass
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(web)))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f'http://10.0.2.2:{server.server_port}'
        installer = (ROOT / 'install.sh').read_text()
        original = 'https://github.com/RATOR2000/csqtt-openwrt/releases/download/'
        require(original in installer, 'Installer fixture URL seam changed')
        installer = installer.replace(original, url + '/')
        installer = installer.replace('https://github.com/RATOR2000/csqtt-openwrt/releases/latest/download', url + '/ci-private')
        (web / 'install.sh').write_text(installer, newline='\n')
        shutil.copyfile(ROOT / 'scripts/test-openwrt-guest.sh', web / 'guest.sh')
        image_name = f'openwrt-{version}-x86-64-generic-ext4-combined.img.gz'
        compressed = work / image_name
        phase('image_download')
        bundle.download(f'https://downloads.openwrt.org/releases/{version}/targets/x86/64/' + image_name,
                        compressed, IMAGES[version])
        disk = work / 'guest.img'
        phase('image_extract')
        image_extraction = extract_openwrt_image(compressed, disk, IMAGES[version])
        phase('disk_prepare')
        test_disk = expand_disposable_root(disk, work)
        private_key = work / 'ssh-key'
        phase('ssh_key')
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(private_key)], check=True, capture_output=True)
        public_key = private_key.with_suffix('.pub').read_text().strip()
        port = free_port()
        phase('clean_firmware_boot')
        guest = pexpect.spawn('qemu-system-x86_64', ['-accel', 'tcg', '-m', '768', '-smp', '2',
            '-drive', f'file={disk},format=raw,if=virtio', '-nographic', '-no-reboot',
            '-netdev', f'user,id=net0,hostfwd=tcp:127.0.0.1:{port}-:22',
            '-device', 'virtio-net-pci,netdev=net0'], encoding='utf-8', timeout=180)
        try:
            prepare_guest_console(guest, public_key, phase, timeout_error=pexpect.TIMEOUT)
            ssh = ['ssh', '-i', str(private_key), '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
                   '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=' + str(work / 'known_hosts'),
                   '-o', 'ConnectTimeout=3', '-p', str(port), 'root@127.0.0.1']
            remote = functools.partial(run_remote, ssh)
            deadline = time.monotonic() + 90
            while remote('true', timeout=6, check=False).returncode:
                require(time.monotonic() < deadline, 'Disposable VM SSH readiness timed out')
                time.sleep(1)
            phase('bootstrap_and_signature_rejection')
            remote(f'mkdir -p /tmp/csqtt-native; cd /tmp/csqtt-native; wget -q {url}/install.sh -O install.sh; wget -q {url}/guest.sh -O guest.sh; test -s install.sh; test -s guest.sh; sha256sum /etc/config/dhcp /etc/config/firewall /etc/config/network > before.sha256')
            signature = fixture / 'catalogue.sig'
            valid_signature = signature.read_bytes()
            signature.write_bytes(b'wrong signature fixture')
            rejected = remote('cd /tmp/csqtt-native; ' + PRIVATE_TRACE + ' > reject.private.log 2>&1', check=False)
            require_signature_rejection(remote, rejected)
            remote('test ! -e /etc/csqtt/installer-bootstrap; test ! -e /etc/csqtt/installer-transaction; cd /tmp/csqtt-native; sha256sum -c before.sha256 >/dev/null')
            signature.write_bytes(valid_signature)
            phase('first_offline_install')
            remote('cd /tmp/csqtt-native; ' + PRIVATE_TRACE + ' > install.private.log 2>&1')
            phase('test_timeout_provision')
            provision_timeout(ssh, test_timeout, '/tmp/csqtt-native')
            phase('native_runtime_dns_firewall_luci')
            smoke = remote(guest_smoke_command('/tmp/csqtt-native'))
            require(smoke.stdout.strip() == 'CSQTT_GUEST_SMOKE_PASS', 'Native runtime/DNS/firewall/LuCI guest proof missing')
            # The actual production installer mandates native --no-network
            # staging and install; only authenticated release assets use HTTP.
            phase('repeat_install_settings_preserved')
            remote('cd /tmp/csqtt-native; sha256sum -c before.sha256 >/dev/null; uci set csqtt.main.workers=18; uci commit csqtt; sha256sum /etc/config/csqtt /etc/config/dhcp /etc/config/firewall /etc/config/network > repeat.sha256; sh install.sh ci-private > repeat.private.log 2>&1; sha256sum -c repeat.sha256 >/dev/null')
            result = {'schema': 1, 'kind': 'clean_openwrt_vm', 'result': 'pass',
                      'source_commit': evidence.source(), 'profile_id': args.profile, 'openwrt': version,
                      'package_manager': platform['package_manager'], 'physical_device': False,
                      'image': {'name': image_name, 'sha256': IMAGES[version], 'extraction': image_extraction,
                                'test_disk': test_disk},
                      'packages': evidence.package_binding(manifest), 'checks': sorted(evidence.VM_CHECKS)}
            output.write_text(json.dumps(result, indent=2) + '\n')
        finally:
            guest.terminate(force=True)
            guest.close(force=True)
            server.shutdown()
            server.server_close()
    print('Clean OpenWrt VM signed installer/offline dependencies/reinstall/native runtime acceptance passed; no physical router or VK proof.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit(failure_message(error)) from None
