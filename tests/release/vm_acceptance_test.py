#!/usr/bin/env python3
"""Mock the SSH transport while executing the real local POSIX shell contract."""
import contextlib
import importlib.util
import io
import os
import pathlib
import re
import select
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('native_vm', ROOT / 'scripts/test-openwrt-vm.py')
native_vm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native_vm)
import vm_console
import vm_timeout
NONCE = 'a' * 32


class ConsoleTimeout(Exception):
    pass


STEP_PHASES = ['boot_network_config_wait', 'boot_authorized_key', 'boot_network_uci',
               'boot_dropbear_restart', 'boot_network_restart']
SH = shutil.which('sh')
if not SH:
    git = pathlib.Path(shutil.which('git') or '')
    candidate = git.parent.parent / 'usr/bin/sh.exe'
    SH = str(candidate) if candidate.is_file() else None


class VmAcceptanceTest(unittest.TestCase):
    @unittest.skipUnless(SH, 'A POSIX shell is required for native uclient option behavior')
    def test_guest_web_root_control_works_with_stock_uclient_without_server_response_option(self):
        guest = (ROOT / 'scripts/test-openwrt-guest.sh').read_text(encoding='utf-8')
        control = re.search(r'(?m)^        if timeout 3 wget[^\n]+\n[\s\S]+?^        else[^\n]+fi', guest).group(0)
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            harness = ('set -eu\nTMP=' + shlex.quote(directory.as_posix()) + '\n'
                       'timeout() { shift; "$@"; }\n'
                       # The native uclient wget supports -O but rejects GNU/BusyBox -S.
                       'wget() { [ "$1" = -O ] || return 64; [ "$#" = 3 ] || return 64; '
                       'case "$3" in */cgi-bin/luci/) if [ "$MODE" = failure ]; then '
                       'printf "%s\\n" "HTTP error 500 private-fixture" >&2; return 8; fi ;; esac; '
                       'printf "%s\\n" "successful-response" > "$2"; }\n'
                       'luci_diagnostics() { printf "diagnostic_exit=%s\\n" "$1"; }\n'
                       'fail() { exit 91; }\n'
                       'if wget -S -O "$TMP/rejected" http://127.0.0.1/; then exit 66; '
                       'else [ "$?" = 64 ] || exit 67; fi\n')
            result = subprocess.run([SH], input=harness + 'MODE=success\n' + control,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, 'CSQTT_GUEST_WEB_CHECK=root_http_ok\n')

    def login_http_fixture(self, body=None, headers=None, status='403 Forbidden'):
        if body is None:
            body = ('<html><form method="post"><input name="luci_username" type="text">'
                    '<input type="password" name="luci_password"></form></html>')
        if headers is None:
            headers = ['X-LuCI-Login-Required: yes', 'Content-Type: text/html; charset=UTF-8']
        return ('HTTP/1.0 ' + status + '\r\n' + '\r\n'.join(headers) + '\r\n\r\n' + body).encode('utf-8')

    def test_guest_luci_parser_requires_complete_native_login_contract(self):
        guest = (ROOT / 'scripts/test-openwrt-guest.sh').read_text(encoding='utf-8')
        program = re.search(r'login_response\(\) \{\n    LC_ALL=C awk -v response_bytes="\$1" \'([\s\S]+?)\' "\$TMP/luci-before"', guest).group(1)
        awk = shutil.which('awk') or (str(pathlib.Path(SH).with_name('awk.exe')) if SH else '')
        if not pathlib.Path(awk).is_file():
            self.skipTest('A native awk is required for the real HTTP parser')
        commands = [[awk, '-v', 'BINMODE=3']]
        if shutil.which('busybox'):
            commands.append([shutil.which('busybox'), 'awk'])
        good = self.login_http_fixture()
        variants = [(good, True), (good.replace(b'X-LuCI-Login-Required: yes', b'x-luci-login-required:\tYeS'), True)]
        # HTML's html/body end tags are optional. Complete form and framing remain required.
        variants.extend([(good.replace(b'</html>', b''), True),
                         (good.replace(b'</html>', b'</html><!-- valid trailing comment -->'), True),
                         (good.replace(b'<html>', b'<!DOCTYPE html>').replace(b'</html>', b''), True),
                         (good.replace(b'<html>', b'').replace(b'</html>', b''), False)])
        body = '<html>Русский<form method="post"><input name="luci_username"><input name="luci_password" type="password"></form></html>'
        variants.append((self.login_http_fixture(body, ['X-LuCI-Login-Required: yes', 'Content-Type: text/html',
                         'Content-Length: ' + str(len(body.encode('utf-8')))]), True))
        for old, new in ((b'403 Forbidden', b'200 OK'), (b'403 Forbidden', b'500 Internal Server Error'),
                         (b'403 Forbidden', b'302 Found'), (b'X-LuCI-Login-Required: yes\r\n', b''),
                         (b'X-LuCI-Login-Required: yes', b'X-LuCI-Login-Required: no'),
                         (b'Content-Type: text/html', b'Content-Type: text/plain'),
                         (b'name="luci_password"', b'name="other"'), (b'type="password"', b'type="text"'),
                         (b'<form method="post">', b'<form method="get">'), (b'</form>', b''),
                         (b'\r\n', b'\n')):
            variants.append((good.replace(old, new), False))
        for extra in ('X-LuCI-Login-Required: yes', 'Content-Length: 0', 'Content-Length: 99999',
                      'Content-Length: private', 'Transfer-Encoding: chunked'):
            variants.append((good.replace(b'\r\n\r\n', ('\r\n' + extra + '\r\n\r\n').encode()), False))
        variants.extend([(self.login_http_fixture(''), False),
                         (self.login_http_fixture('<html>Forbidden</html>'), False),
                         (self.login_http_fixture('<html><form method="post"></form><input name="luci_username"><input type="password" name="luci_password"></html>'), False)])
        for command in commands:
            for response, accepted in variants:
                result = subprocess.run(command + ['-v', 'response_bytes=' + str(len(response)), program],
                                        input=response, capture_output=True, timeout=10, env=dict(os.environ, LC_ALL='C'))
                self.assertEqual(result.returncode == 0, accepted, result.stderr)
                if accepted:
                    self.assertEqual(result.stdout, b'')
                else:
                    self.assertTrue(native_vm.guest_web_diagnostics(result.stdout.decode())['parse'])

    @unittest.skipUnless(SH and sys.platform != 'win32', 'Linux FIFO transport runs in native CI')
    def test_guest_luci_raw_transport_keeps_nc_exit_and_read_bound(self):
        guest = (ROOT / 'scripts/test-openwrt-guest.sh').read_text(encoding='utf-8')
        functions = guest[guest.index('login_response() {'):guest.index('stage luci_http\n')]
        tools = {}
        for name in ('awk', 'cat', 'rm', 'wc', 'mkfifo'):
            path = shutil.which(name) or str(pathlib.Path(SH).with_name(name + '.exe'))
            if not pathlib.Path(path).is_file():
                self.skipTest('Native shell tools are required for the real bounded reader')
            tools[name] = pathlib.Path(path).as_posix()
        aliases = ''.join(name + '() { ' + shlex.quote(path) + (' -v BINMODE=3' if name == 'awk' else '') +
                          ' "$@"; };\n' for name, path in tools.items())
        dd = shutil.which('dd') or str(pathlib.Path(SH).with_name('dd.exe'))
        if pathlib.Path(dd).is_file():
            aliases += 'dd() { ' + shlex.quote(pathlib.Path(dd).as_posix()) + ' "$@"; };\n'
        else:
            # Windows Git omits dd; its real head still exercises the byte cap
            # and pipeline/status contract. Linux uses the actual dd command.
            head = shutil.which('head') or str(pathlib.Path(SH).with_name('head.exe'))
            if not pathlib.Path(head).is_file():
                self.skipTest('A native bounded byte reader is required')
            aliases += ('dd() { [ "$#" = 2 ] && [ "$1" = bs=1 ] && [ "$2" = count=131073 ] || return 78; ' +
                        shlex.quote(pathlib.Path(head).as_posix()) + ' -c 131073; };\n')
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            fixture = directory / 'fixture'
            harness = ('set -eu\nTMP=' + shlex.quote(directory.as_posix()) + '\n' + aliases +
                       'timeout() { [ "$1" = 10 ] || return 77; shift; "$@"; }\n'
                       'nc() { [ "$#" = 2 ] && [ "$1" = 127.0.0.1 ] && [ "$2" = 80 ] || return 76; '
                       ': > "$TMP/sent-request"; while IFS= read -r line; do printf "%s\\n" "$line" >> "$TMP/sent-request"; '
                       '[ "$line" != "$(printf "\\r")" ] || break; done; '
                       'cat "$TMP/fixture"; return "$NC_EXIT"; }\n'
                       'luci_diagnostics() { printf "diagnostic_exit=%s\\n" "$1"; }\n'
                       'fail() { exit 91; }\n' + functions)
            for payload, exit_code, expected in ((self.login_http_fixture(), 0, 0),
                                                  (self.login_http_fixture(), 4, 91),
                                                  (self.login_http_fixture(status='500 Internal Server Error'), 0, 91),
                                                  (self.login_http_fixture() + b'x' * 131073, 0, 91)):
                fixture.write_bytes(payload)
                result = subprocess.run([SH], input=harness + '\nNC_EXIT=' + str(exit_code) + '\nluci_http\n',
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertNotIn('<html>', result.stdout)
                self.assertLessEqual((directory / 'luci-before').stat().st_size, 131073)
                self.assertEqual((directory / 'sent-request').read_bytes(),
                                 b'GET /cgi-bin/luci/ HTTP/1.0\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n')
            fixture.write_bytes(self.login_http_fixture())
            result = subprocess.run([SH], input=harness + '\ndd() { return 1; }\nNC_EXIT=0\nluci_http\n',
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 91, result.stderr)

    @unittest.skipUnless(sys.platform == 'linux', 'Actual BusyBox nc/FIFO and delayed HTTP peer run on Linux')
    def test_guest_luci_actual_nc_keeps_request_open_until_delayed_response(self):
        busybox = shutil.which('busybox')
        self.assertIsNotNone(busybox, 'Native Linux acceptance requires busybox-static')
        capability = subprocess.run([busybox, 'nc', '--help'], capture_output=True, timeout=3)
        help_output = capability.stdout + capability.stderr
        if capability.returncode in (1, 127) and re.search(rb'(?m)^nc: applet not found\r?$', help_output):
            self.skipTest('Host BusyBox omits nc; required Linux FIFO test and real OpenWrt guest nc acceptance still run')
        self.assertIn(b'Usage: nc', help_output,
                      'Host nc capability failure rc=' + str(capability.returncode) + ' stderr=' + repr(capability.stderr[:1024]))
        guest = (ROOT / 'scripts/test-openwrt-guest.sh').read_text(encoding='utf-8')
        functions = guest[guest.index('login_response() {'):guest.index('stage luci_http\n')]
        response = self.login_http_fixture()
        @contextlib.contextmanager
        def peer():
            result = []
            server = socket.socket()
            server.bind(('127.0.0.1', 0))
            server.listen(1)
            server.settimeout(0.1)
            stopping = threading.Event()
            def handle():
                try:
                    while not stopping.is_set():
                        try:
                            connection, _ = server.accept()
                            break
                        except socket.timeout:
                            continue
                    else:
                        return
                    with connection:
                        connection.settimeout(3)
                        data = b''
                        while not data.endswith(b'\r\n\r\n'):
                            chunk = connection.recv(1024)
                            if not chunk or len(data) > 8192:
                                result.append('incomplete_request')
                                return
                            data += chunk
                        # Reproduce a CGI server that aborts when the client
                        # half-closes while it is preparing a response.
                        ready, _, _ = select.select([connection], [], [], 0.15)
                        if ready and connection.recv(1) == b'':
                            result.append('early_fin')
                            return
                        connection.sendall(response)
                        result.append('response')
                except OSError:
                    result.append('server_error')
            thread = threading.Thread(target=handle, daemon=True)
            thread.start()
            try:
                yield server.getsockname()[1], result
            finally:
                stopping.set()
                server.close()
                thread.join(1)
                if sys.exc_info()[0] is None:
                    self.assertFalse(thread.is_alive(), 'HTTP fixture must finish without a sleeping writer')
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            binary = vm_timeout.build_timeout(directory)
            request = b'GET /cgi-bin/luci/ HTTP/1.0\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n'
            with peer() as (port, state):
                old = subprocess.run([str(binary), '2', busybox, 'nc', '127.0.0.1', str(port)],
                                     input=request, capture_output=True, timeout=4)
                self.assertEqual(old.returncode, 0, 'Host nc start rc=' + str(old.returncode) + ' stderr=' + repr(old.stderr[:1024]))
                self.assertEqual(old.stdout, b'')
                self.assertEqual(state, ['early_fin'])
            with peer() as (port, state):
                private_bin = directory / 'bin'
                private_bin.mkdir()
                wrapper = private_bin / 'nc'
                invoked = directory / 'nc-invoked'
                wrapper.write_text('#!/bin/sh\n'
                                   '[ "$#" = 2 ] && [ "$1" = 127.0.0.1 ] && [ "$2" = 80 ] || exit 76\n'
                                   ': > ' + shlex.quote(str(invoked)) + '\nexec ' +
                                   shlex.quote(busybox) + ' nc 127.0.0.1 ' + str(port) + '\n', encoding='utf-8')
                wrapper.chmod(0o700)
                harness = ('set -eu\nTMP=' + shlex.quote(directory.as_posix()) + '\n' +
                           'PATH=' + shlex.quote(str(private_bin)) + ':"$PATH"; export PATH\n' +
                           'timeout() { ' + shlex.quote(str(binary)) + ' "$@"; }\n' +
                           'luci_diagnostics() { printf "diagnostic_exit=%s\\n" "$1"; }\n'
                           'fail() { exit 91; }\n' + functions + '\nluci_http\n')
                start = time.monotonic()
                fixed = subprocess.run([SH], input=harness, capture_output=True, text=True, timeout=5)
                elapsed = time.monotonic() - start
                self.assertTrue(invoked.is_file(), 'Native timeout execvp must reach the private nc executable via PATH')
                self.assertEqual(fixed.returncode, 0, fixed.stdout + fixed.stderr)
                self.assertEqual(state, ['response'])
            self.assertLess(elapsed, 3, 'Successful probes must not wait for the ten-second deadline')
            self.assertFalse((directory / 'web-input').exists())

    def test_guest_web_filter_redacts_native_http_body_and_system_log(self):
        guest = (ROOT / 'scripts/test-openwrt-guest.sh').read_text(encoding='utf-8')
        program = re.search(r"web_filter\(\) \{\n    awk '([\s\S]+?)'\n\}", guest).group(1)
        awk = shutil.which('awk') or (str(pathlib.Path(SH).with_name('awk.exe')) if SH else '')
        if not pathlib.Path(awk).is_file():
            self.skipTest('A native awk is required for safe guest diagnostics')
        commands = [[awk]]
        if shutil.which('busybox'):
            commands.append([shutil.which('busybox'), 'awk'])
        private = 'private-key-password-url-config'
        body = ('HTTP/1.1 500 Internal Server Error\nLocation: https://example.invalid/' + private +
                '\nHTTP error 403\nConnection refused: ' + private + '\nPermission denied: ' + private +
                '\nInvalid SSL certificate: ' + private + '\nServer hostname does not match SSL certificate: ' + private + '\nType error: ' + private + '\nUnable to resolve module ' + private +
                '\nIn /usr/share/ucode/luci/dispatcher.uc, line 14, byte 1:\n' +
                'In /usr/share/csqtt/runtime.uc, line 12, byte 2:\n' +
                'In /private/runtime.uc, line 1, byte 1:\n' +
                'In /usr/share/ucode/luci/runtime.uc, line 99999, byte 2:\n' + private)
        for command in commands:
            result = subprocess.run(command + [program], input=body, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(private, result.stdout)
            self.assertNotIn('https:', result.stdout)
            parsed = native_vm.guest_web_diagnostics(result.stdout)
            self.assertEqual(parsed['status'], [403, 500])
            self.assertEqual(parsed['classes'], ['connection_refused', 'module_error', 'permission_denied', 'tls_certificate', 'tls_hostname', 'type_error'])
            self.assertEqual(parsed['locations'], [('csqtt.runtime', 12), ('luci.dispatcher', 14)])

    def test_guest_web_markers_reject_unowned_fields_paths_and_values(self):
        body = ('CSQTT_GUEST_WEB_EXIT=256\nCSQTT_GUEST_WEB_SERVICE_EXIT=-1\nCSQTT_GUEST_WEB_STATUS=600\n'
                'CSQTT_GUEST_WEB_BYTES=131074\nCSQTT_GUEST_WEB_BYTES=-1\nCSQTT_GUEST_WEB_READ_EXIT=256\n'
                'CSQTT_GUEST_WEB_PARSE=private\nCSQTT_GUEST_WEB_PARSE=auth_header private\n'
                'CSQTT_GUEST_WEB_CHECK=private\nCSQTT_GUEST_WEB_CHECK=port80_closed private\n'
                'CSQTT_GUEST_WEB_FILE=/etc/config/private:missing\nCSQTT_GUEST_WEB_MODULE=private:loaded\n'
                'CSQTT_GUEST_WEB_CLASS=private\nCSQTT_GUEST_WEB_SOURCE=/private/runtime.uc:1\n'
                'CSQTT_GUEST_WEB_SOURCE=luci.runtime:20001\nCSQTT_GUEST_WEB_SOURCE=luci.runtime:0\n')
        self.assertTrue(all(not values for values in native_vm.guest_web_diagnostics(body).values()))
        good = ('CSQTT_GUEST_WEB_EXIT=124\r\nCSQTT_GUEST_WEB_SERVICE_EXIT=1\nCSQTT_GUEST_WEB_CGI_EXIT=2\nCSQTT_GUEST_WEB_STATUS=500\n'
                'CSQTT_GUEST_WEB_BYTES=0\nCSQTT_GUEST_WEB_BYTES=131073\nCSQTT_GUEST_WEB_READ_EXIT=1\nCSQTT_GUEST_WEB_PARSE=auth_header\n'
                'CSQTT_GUEST_WEB_CHECK=port80_listening\nCSQTT_GUEST_WEB_FILE=cgi:present\n'
                'CSQTT_GUEST_WEB_MODULE=ubus:loaded\nCSQTT_GUEST_WEB_SOURCE=luci.dispatcher:1\n')
        parsed = native_vm.guest_web_diagnostics(good)
        self.assertEqual(parsed['exit'], [124])
        self.assertEqual(parsed['service_exit'], [1])
        self.assertEqual(parsed['cgi_exit'], [2])
        self.assertEqual(parsed['bytes'], [0, 131073])
        self.assertEqual(parsed['read_exit'], [1])
        self.assertEqual(parsed['parse'], ['auth_header'])
        self.assertEqual(parsed['status'], [500])
        self.assertEqual(parsed['checks'], ['port80_listening'])
        self.assertEqual(parsed['files'], ['cgi:present'])
        self.assertEqual(parsed['modules'], ['ubus:loaded'])
        self.assertEqual(parsed['locations'], [('luci.dispatcher', 1)])
        self.assertTrue(all(not values for values in native_vm.guest_web_diagnostics(good + 'x' * native_vm.DIAGNOSTIC_LIMIT).values()))

    def test_guest_web_transport_prints_only_fixed_diagnostic_markers(self):
        private = 'private-key-password-url-config'
        body = ('CSQTT_GUEST_WEB_EXIT=8\nCSQTT_GUEST_WEB_STATUS=500\n'
                'CSQTT_GUEST_WEB_BYTES=0\nCSQTT_GUEST_WEB_READ_EXIT=0\nCSQTT_GUEST_WEB_PARSE=body_size\n'
                'CSQTT_GUEST_WEB_CHECK=uhttpd_running\nCSQTT_GUEST_WEB_CLASS=module_error\n'
                'CSQTT_GUEST_WEB_SOURCE=luci.dispatcher:14\n' + private + '\n')
        with mock.patch.object(native_vm, 'PHASE', 'native_runtime_dns_firewall_luci'), \
                mock.patch.object(native_vm.subprocess, 'run', side_effect=[
                    subprocess.CompletedProcess(['ssh'], 1, stdout='', stderr=''),
                    subprocess.CompletedProcess(['ssh'], 0,
                        stdout=(body + '\n' + native_vm.DIAGNOSTIC_READ_OK + '\n').encode(), stderr=b'')]), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(ValueError):
                native_vm.run_remote(['ssh'], 'false')
        for expected in ('web exit: 8', 'web status: 500', 'web checks: uhttpd_running',
                         'web bytes: 0', 'web read_exit: 0', 'web parse: body_size',
                         'web classes: module_error', 'web locations: luci.dispatcher:14'):
            self.assertIn(expected, output.getvalue())
        self.assertNotIn(private, output.getvalue())

    def test_first_install_native_errors_excludes_traces_and_redacts_values(self):
        private = 'private-password-key-url-identity'
        text = ('+CSQTT_XTRACE:1: apk ' + private + '\nERROR: opening /tmp/' + private +
                ' password="' + private + '" https://example.invalid/' + private + '\n' +
                'ERROR: checksum ' + 'a' * 64 + '\n' + 'WARNING: fixed\n' * 10)
        result = native_vm.first_install_native_errors(text)
        self.assertEqual(len(result), 6)
        self.assertNotIn(private, repr(result))
        self.assertNotIn('CSQTT_XTRACE', repr(result))
        self.assertNotIn('a' * 64, repr(result))
        self.assertIn('ERROR: opening <path> password=<redacted> <url>', result)

    def test_guest_trace_metadata_handles_shell_variants_without_exposing_arguments(self):
        private = 'private-password-key-url-identity'
        for prefix, expected in (('+CSQTT_GUEST_TRACE:90: ', 'owned'), ('++CSQTT_GUEST_TRACE:0: ', 'owned'), ('+ ', 'default')):
            result = native_vm.guest_trace_metadata(prefix + 'ucode ' + private + '\n' + prefix + 'fail\n' + prefix + 'grep cleanup\n')
            self.assertEqual(result['format'], expected)
            self.assertEqual(result['command'], 'ucode')
            self.assertNotIn(private, repr(result))
        self.assertEqual(native_vm.guest_trace_metadata('+CSQTT_GUEST_TRACE:99999: ' + private)['command'], 'unknown')

    def test_pinned_apk_setup_templates_emit_fixed_classes_without_native_values(self):
        private = 'private-password-key-url-identity'
        for category, message in (
                ('database_open', 'Failed to open apk database:'),
                ('database_lock', 'Unable to lock database'),
                ('cache_setup', 'Unable to setup the cache'),
                ('package_extract', 'failed to extract '),
                ('repository_format', 'repositories file syntax error'),
                ('unsupported_format', 'file format is invalid or inconsistent'),
                ('integrity_error', 'ADB integrity error'),
                ('unsupported_root', 'uvol not supported with --root'),
                ('option_argument', 'invalid argument for option')):
            with self.subTest(category=category):
                result = native_vm.project_stage_diagnostics(message + ' ' + private)
                self.assertIn(category, result['classes'])
                self.assertNotIn(private, repr(result))

    def test_native_output_head_is_checked_bounded_and_stops_at_next_trace(self):
        if not SH:
            self.skipTest('A POSIX shell is required')
        source = (ROOT / 'install.sh').read_text(encoding='utf-8').splitlines()
        line = next(n for n, row in enumerate(source, 1) if row.strip().startswith(
            'apk --root "$CS_PM_ROOT" --arch "$CS_ARCH" --repositories-file "$CS_REPOSITORIES"'))
        marker = '+CSQTT_XTRACE:' + str(line) + ': apk private-arguments\n'
        with tempfile.TemporaryDirectory() as directory:
            log = pathlib.Path(directory) / 'stage.log'
            awk = shutil.which('awk') or str(pathlib.Path(SH).with_name('awk.exe'))
            wc = shutil.which('wc') or str(pathlib.Path(SH).with_name('wc.exe'))
            command = ('awk() { ' + shlex.quote(awk) + ' "$@"; }; wc() { ' + shlex.quote(wc) +
                       ' "$@"; }; f=' + shlex.quote(log.as_posix()) + '; ' + native_vm._private_native_output_head())
            def run(body):
                log.write_text(body, encoding='utf-8')
                return subprocess.run([SH], input=command, text=True, capture_output=True, timeout=10)
            good = run('earlier private data\n' + marker + 'apk: unrecognized option\n' + 'usage\n' * 4000 +
                       '+CSQTT_XTRACE:1: other private-data\n')
            self.assertEqual(good.returncode, 0, good.stderr)
            self.assertTrue(good.stdout.startswith('apk: unrecognized option\n'))
            self.assertNotIn('private', good.stdout)
            self.assertLessEqual(len(good.stdout.encode()), native_vm.DIAGNOSTIC_LIMIT + len('\n' + native_vm.DIAGNOSTIC_READ_OK + '\n'))
            stopped = run(marker + 'first\n+CSQTT_XTRACE:1: next secret\nprivate\n')
            self.assertEqual(stopped.stdout, 'first\n\n' + native_vm.DIAGNOSTIC_READ_OK + '\n')
            for bad in ('no marker\n', marker + marker, marker + 'x' * (native_vm.DIAGNOSTIC_SCAN_LIMIT + 1)):
                result = run(bad)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(native_vm.DIAGNOSTIC_READ_OK, result.stdout)

    @contextlib.contextmanager
    def nested_solver_fixture(self, relative='bootstrap/solver.log'):
        if not SH:
            self.skipTest('A POSIX shell is required for checked nested discovery')
        tools = {}
        for name in ('wc', 'awk'):
            path = shutil.which(name) or str(pathlib.Path(SH).with_name(name + '.exe'))
            if not pathlib.Path(path).is_file():
                self.skipTest('Native wc/awk are required for checked nested discovery')
            tools[name] = pathlib.Path(path).as_posix()
        with tempfile.TemporaryDirectory(prefix='csqtt-nested-') as temporary:
            directory = pathlib.Path(temporary)
            phase_log = directory / 'csqtt-native/install.private.log'
            phase_log.parent.mkdir()
            root = directory / 'csqtt-portable.Ab1234'
            (root / 'bootstrap').mkdir(parents=True)
            (root / relative).write_text('synthetic-private-solver', encoding='utf-8')
            source = (ROOT / 'install.sh').read_text(encoding='utf-8').splitlines()
            line = next(number for number, text in enumerate(source, 1)
                        if text.strip() == 'CS_TMP=$(mktemp -d /tmp/csqtt-portable.XXXXXX)')
            trace = '+CSQTT_XTRACE:' + str(line) + ': CS_TMP=' + root.as_posix() + '\n'
            phase_log.write_text(trace, encoding='utf-8')
            with mock.patch.object(native_vm, 'PHASE', 'first_offline_install'):
                command = (native_vm.bootstrap_solver_read_command() if relative == 'bootstrap/solver.log' else
                           native_vm.project_stage_read_command()).replace('/tmp', directory.as_posix())
            aliases = ''.join(name + '() { ' + shlex.quote(path) + ' "$@"; }; ' for name, path in tools.items())
            # The existing native-dd test checks byte reading. This strict shell
            # double lets Windows independently exercise discovery and refusal.
            reader = ('dd() { [ "$#" = 4 ] && [ "$1" = ' +
                      shlex.quote('if=' + (root / relative).as_posix()) +
                      ' ] && [ "$2" = bs=1 ] && [ "$3" = skip=0 ] && [ "$4" = count=8192 ] || return 99; '
                      'printf "%s\\n" "Unknown package openssl-util"; }; ')
            def run(prefix=''):
                return subprocess.run([SH], input=aliases + reader + prefix + command,
                                      encoding='utf-8', capture_output=True, timeout=10)
            yield directory, root, phase_log, trace, run

    def test_nested_solver_discovery_checks_exact_source_assignment_and_bounded_scan(self):
        with self.nested_solver_fixture() as (directory, root, log, trace, run):
            for ending in ('\n', '\r\n'):
                log.write_text(trace.rstrip('\n') + ending, encoding='utf-8', newline='')
                result = run()
                self.assertEqual(result.returncode, 0)
                self.assertTrue(result.stdout.endswith('\n' + native_vm.DIAGNOSTIC_READ_OK + '\n'))
            variants = ('', trace + trace, trace.replace('CS_TMP=', 'OTHER_TMP='),
                        trace.replace('Ab1234', 'Ab1234/escape'), trace.replace('Ab1234', 'A_1234'),
                        trace.replace('CSQTT_XTRACE:', 'CSQTT_XTRACE:9'),
                        trace + 'x' * native_vm.DIAGNOSTIC_SCAN_LIMIT)
            for text in variants:
                with self.subTest(text=text[:80]):
                    log.write_text(text, encoding='utf-8')
                    result = run()
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(native_vm.DIAGNOSTIC_READ_OK, result.stdout)
            log.write_text(trace, encoding='utf-8')
            for tool in ('wc', 'awk', 'dd'):
                with self.subTest(tool=tool):
                    result = run(tool + '() { return 1; }; ')
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(native_vm.DIAGNOSTIC_READ_OK, result.stdout)
            with mock.patch.object(native_vm, 'PHASE', 'host_preflight'):
                self.assertEqual(native_vm.bootstrap_solver_read_command(), 'exit 1')

    def test_nested_solver_reader_refuses_symlinked_log_and_each_directory(self):
        with self.nested_solver_fixture() as (directory, root, log, trace, run):
            for path in (root / 'bootstrap/solver.log', root / 'bootstrap', root, log, log.parent):
                backing = path.with_name(path.name + '-backing')
                path.rename(backing)
                try:
                    try:
                        path.symlink_to(backing, target_is_directory=backing.is_dir())
                    except OSError:
                        if sys.platform == 'win32':
                            self.skipTest('Windows symlink privilege unavailable; Linux CI exercises every path guard')
                        raise
                    result = run()
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn(native_vm.DIAGNOSTIC_READ_OK, result.stdout)
                finally:
                    if path.is_symlink():
                        path.unlink()
                    backing.rename(path)

    def test_project_stage_reader_requires_exact_bounded_phase_root_and_checked_read(self):
        with self.nested_solver_fixture('stage.log') as (directory, root, log, trace, run):
            self.assertEqual(run().returncode, 0)
            variants = ('', trace + trace, trace.replace('CS_TMP=', 'OTHER_TMP='),
                        trace.replace('CSQTT_XTRACE:', 'CSQTT_XTRACE:9'),
                        trace.replace('Ab1234', 'Ab1234/escape'),
                        trace.replace('Ab1234', '$(printf injected)'),
                        trace + 'x' * native_vm.DIAGNOSTIC_SCAN_LIMIT)
            for text in variants:
                with self.subTest(text=text[:80]):
                    log.write_text(text, encoding='utf-8')
                    result = run()
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn(native_vm.DIAGNOSTIC_READ_OK, result.stdout)
                    self.assertNotIn('injected', result.stdout)
            log.write_text(trace, encoding='utf-8')
            for prefix in ('wc() { return 1; }; ', 'wc() { printf "not-numeric\\n"; }; ',
                           'awk() { return 1; }; ', 'dd() { return 1; }; '):
                result = run(prefix)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(native_vm.DIAGNOSTIC_READ_OK, result.stdout)
            (root / 'stage.log').unlink()
            result = run()
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(native_vm.DIAGNOSTIC_READ_OK, result.stdout)
        for phase in ('host_preflight', 'bootstrap_and_signature_rejection', 'native_runtime_dns_firewall_luci'):
            with self.subTest(phase=phase), mock.patch.object(native_vm, 'PHASE', phase):
                self.assertEqual(native_vm.project_stage_read_command(), 'exit 1')
        self.assertEqual(native_vm._nested_log_read_command('../private.log'), 'exit 1')

    def test_project_stage_reader_refuses_symlinked_stage_log_and_each_directory(self):
        with self.nested_solver_fixture('stage.log') as (directory, root, log, trace, run):
            for path in (root / 'stage.log', root, log, log.parent):
                backing = path.with_name(path.name + '-backing')
                path.rename(backing)
                try:
                    try:
                        path.symlink_to(backing, target_is_directory=backing.is_dir())
                    except OSError:
                        if sys.platform == 'win32':
                            self.skipTest('Windows symlink privilege unavailable; Linux CI exercises every path guard')
                        raise
                    result = run()
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn(native_vm.DIAGNOSTIC_READ_OK, result.stdout)
                finally:
                    if path.is_symlink():
                        path.unlink()
                    backing.rename(path)

    def test_project_stage_classification_exposes_only_fixed_native_classes_and_source_known_names(self):
        private = 'private-password-key-url-identity'
        text = ('ERROR: unable to select packages:\n  csqtt (no such package)\n'
                '  csqtt-captcha-0.1: breaks: luci-app-csqtt\n'
                'UNTRUSTED signature\nNo space left on device\n'
                ' * opkg_install_cmd: Cannot install package openssl-util.\n'
                'Unknown package ' + private + '\n')
        result = native_vm.project_stage_diagnostics(text)
        self.assertEqual(result['classes'], ['cannot_install', 'dependency_unsatisfied', 'resource_limit',
                                            'signature_rejected', 'unknown_package', 'version_conflict'])
        self.assertEqual(result['packages'], ['csqtt', 'luci-app-csqtt', 'openssl-util'])
        self.assertNotIn(private, str(result))
        source = (ROOT / 'scripts/portable-install.sh').read_text(encoding='utf-8')
        for name in native_vm.PROJECT_STAGE_PACKAGES:
            self.assertIn(name, source)
        self.assertIn("csqtt_portable_die '" + native_vm.PROJECT_STAGE_ERROR.removeprefix('CSQTT: ') + "'", source)
        for text in (private, 'private-csqtt-package', 'csqtt.private-package', 'x' * 2 + 'jsonfilter-suffix'):
            self.assertEqual(native_vm.project_stage_diagnostics(text),
                             {'classes': ['unclassified_output'], 'packages': []})
        self.assertEqual(native_vm.project_stage_diagnostics('')['classes'], ['empty_output'])
        self.assertEqual(native_vm.project_stage_diagnostics(
            'apk: unrecognized option --private\nBAD index\nworld[csqtt]\n'
            'trying to overwrite private\nNo such file or directory\nBAD checksum\n')['classes'],
            ['checksum_mismatch', 'file_conflict', 'file_read', 'index_rejected',
             'unsupported_option', 'world_constraint'])

    def test_project_stage_transport_is_bounded_checked_and_never_prints_private_values(self):
        private = 'private-password-key-url-identity'
        sentinel = ('\n' + native_vm.DIAGNOSTIC_READ_OK + '\n').encode('ascii')
        main = subprocess.CompletedProcess(['ssh'], 0,
                 stdout=native_vm.PROJECT_STAGE_ERROR.encode('utf-8') + sentinel, stderr=b'')
        body = ('ERROR: unable to select packages:\ncsqtt (no such package)\n'
                '+CSQTT_XTRACE:40: csqtt_pm_install ' + private + '\n'
                '+CSQTT_XTRACE:80: ' + private + ' secret\n'
                'install.sh: line 88: tar: not found\n'
                'install.sh: line 90: ' + private + ': parameter not set\n'
                '+CSQTT_XTRACE:100: csqtt_portable_cleanup ' + private + '\n').encode('utf-8')
        cases = ((subprocess.CompletedProcess(['ssh'], 0, stdout=body + sentinel, stderr=b''), True),
                 (subprocess.CompletedProcess(['ssh'], 1, stdout=body + sentinel, stderr=body), False),
                 (subprocess.CompletedProcess(['ssh'], 0, stdout=body, stderr=body), False),
                 (subprocess.CompletedProcess(['ssh'], 0, stdout=b'x' * (native_vm.DIAGNOSTIC_LIMIT + 1) + sentinel,
                                              stderr=body), False),
                 (subprocess.TimeoutExpired(private, 15), False))
        for nested, success in cases:
            with self.subTest(success=success, kind=type(nested).__name__), \
                    mock.patch.object(native_vm, 'PHASE', 'first_offline_install'), \
                    mock.patch.object(native_vm.subprocess, 'run', side_effect=[
                        subprocess.CompletedProcess(['ssh'], 1, stdout='', stderr=''), main, nested]) as transport, \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(ValueError):
                    native_vm.run_remote(['ssh', 'synthetic-host'], 'false')
            self.assertEqual(transport.call_count, 3)
            command = transport.call_args_list[-1].args[0][-1]
            self.assertIn('/stage.log', command)
            self.assertNotIn('/bootstrap/', command)
            self.assertNotIn('eval', command)
            self.assertIn('OpenWrt project stage diagnostics: ' +
                          ('bounded_read_ok' if success else 'diagnostic_unavailable'), output.getvalue())
            self.assertNotIn(private, output.getvalue())
            if success:
                self.assertIn('OpenWrt project stage class: dependency_unsatisfied', output.getvalue())
                self.assertIn('OpenWrt project stage package: csqtt', output.getvalue())
                self.assertIn('OpenWrt project stage trace function: csqtt_pm_install', output.getvalue())
                self.assertIn('OpenWrt project stage trace: generated_source_line=40', output.getvalue())
                self.assertIn('OpenWrt project stage shell error: unset_parameter', output.getvalue())
                self.assertIn('OpenWrt project stage missing tool: tar', output.getvalue())
                self.assertNotIn('csqtt_portable_cleanup', output.getvalue())

    def test_project_stage_read_requires_complete_exact_error_in_checked_current_phase_log(self):
        sentinel = ('\n' + native_vm.DIAGNOSTIC_READ_OK + '\n').encode('ascii')
        for phase, log in (('first_offline_install', ''),
                           ('first_offline_install', native_vm.PROJECT_STAGE_ERROR + ' private-suffix'),
                           ('first_offline_install', 'private-prefix ' + native_vm.PROJECT_STAGE_ERROR),
                           ('bootstrap_and_signature_rejection', native_vm.PROJECT_STAGE_ERROR),
                           ('native_runtime_dns_firewall_luci', native_vm.PROJECT_STAGE_ERROR)):
            with self.subTest(phase=phase, log=log), mock.patch.object(native_vm, 'PHASE', phase), \
                    mock.patch.object(native_vm.subprocess, 'run', side_effect=[
                        subprocess.CompletedProcess(['ssh'], 1, stdout='', stderr=native_vm.PROJECT_STAGE_ERROR),
                        subprocess.CompletedProcess(['ssh'], 0, stdout=log.encode('utf-8') + sentinel, stderr=b'')
                    ]) as transport, contextlib.redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(ValueError):
                    native_vm.run_remote(['ssh', 'synthetic-host'], 'false')
            self.assertEqual(transport.call_count, 2)
            self.assertNotIn('project stage diagnostics:', output.getvalue())

    def test_nested_solver_classification_has_only_fixed_classes_and_source_known_packages(self):
        private = 'private-password-key-url-identity'
        text = ("Unknown package 'openssl-util'.\n * opkg_install_cmd: Cannot install package jsonfilter.\n"
                'Could not open /private/' + private + '\nUnknown package ' + private + '\n')
        result = native_vm.bootstrap_solver_diagnostics(text)
        self.assertEqual(result['classes'], ['unknown_package', 'cannot_install', 'file_read'])
        self.assertEqual(result['packages'], ['openssl-util', 'jsonfilter'])
        self.assertNotIn(private, str(result))
        source = (ROOT / 'scripts/portable-install.sh').read_text(encoding='utf-8')
        for name in native_vm.BOOTSTRAP_PACKAGES:
            self.assertIn(name, source)
        self.assertIn("csqtt_portable_die '" + native_vm.BOOTSTRAP_SOLVER_ERROR.removeprefix('CSQTT: ') + "'", source)
        self.assertEqual(native_vm.bootstrap_solver_diagnostics('private-openssl-util-package')['packages'], [])
        self.assertEqual(native_vm.bootstrap_solver_diagnostics('jsonfilter.private-package')['packages'], [])
        self.assertEqual(native_vm.bootstrap_solver_diagnostics(private)['classes'], ['unclassified_output'])
        self.assertEqual(native_vm.bootstrap_solver_diagnostics('')['classes'], ['empty_output'])

    def test_nested_solver_transport_checks_framing_status_bound_and_never_prints_private_values(self):
        private = 'private-password-key-url-identity'
        sentinel = ('\n' + native_vm.DIAGNOSTIC_READ_OK + '\n').encode('ascii')
        main = subprocess.CompletedProcess(['ssh'], 0,
                 stdout=native_vm.BOOTSTRAP_SOLVER_ERROR.encode('utf-8') + sentinel, stderr=b'')
        body = ("Unknown package 'openssl-util'.\nCould not open /private/" + private).encode('utf-8')
        cases = ((subprocess.CompletedProcess(['ssh'], 0, stdout=body + sentinel, stderr=b''), True),
                 (subprocess.CompletedProcess(['ssh'], 1, stdout=body + sentinel, stderr=body), False),
                 (subprocess.CompletedProcess(['ssh'], 0, stdout=body, stderr=body), False),
                 (subprocess.CompletedProcess(['ssh'], 0, stdout=b'x' * (native_vm.DIAGNOSTIC_LIMIT + 1) + sentinel,
                                              stderr=body), False),
                 (subprocess.TimeoutExpired(private, 15), False))
        for nested, success in cases:
            with self.subTest(success=success, kind=type(nested).__name__), \
                    mock.patch.object(native_vm, 'PHASE', 'first_offline_install'), \
                    mock.patch.object(native_vm.subprocess, 'run', side_effect=[
                        subprocess.CompletedProcess(['ssh'], 1, stdout='', stderr=''), main, nested]) as transport, \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(ValueError):
                    native_vm.run_remote(['ssh', 'synthetic-host'], 'false')
            self.assertEqual(transport.call_count, 3)
            command = transport.call_args_list[-1].args[0][-1]
            self.assertIn('/bootstrap/solver.log', command)
            self.assertNotIn('eval', command)
            self.assertIn('OpenWrt bootstrap solver diagnostics: ' +
                          ('bounded_read_ok' if success else 'diagnostic_unavailable'), output.getvalue())
            self.assertNotIn(private, output.getvalue())
            self.assertNotIn('/private/', output.getvalue())
            if success:
                self.assertIn('OpenWrt bootstrap solver class: unknown_package', output.getvalue())
                self.assertIn('OpenWrt bootstrap solver class: file_read', output.getvalue())
                self.assertIn('OpenWrt bootstrap solver package: openssl-util', output.getvalue())

    def test_private_trace_classification_uses_fixed_functions_and_stops_before_cleanup(self):
        private = 'private_secret_command_key_url'
        trace = ('+CSQTT_XTRACE:40: csqtt_portable_main ' + private + '\n'
                 '+CSQTT_XTRACE:60: csqtt_bootstrap ' + private + '\n'
                 '+CSQTT_XTRACE:80: ' + private + ' secret\n'
                 '+CSQTT_XTRACE:90: csqtt_portable_cleanup ' + private + '\n'
                 '+CSQTT_XTRACE:100: csqtt_bootstrap_rollback ' + private + '\n')
        classified = native_vm.installer_diagnostics(trace)
        self.assertEqual(classified['trace_functions'], ['csqtt_portable_main', 'csqtt_bootstrap'])
        self.assertEqual(classified['trace_last_source_line'], 80)
        self.assertNotIn(private, str(classified))
        self.assertIn('sh -x install.sh ci-private', native_vm.PRIVATE_TRACE)
        self.assertIn('${LINENO:-0}', native_vm.PRIVATE_TRACE)
        self.assertNotIn('sh -x install.sh', (ROOT / 'scripts/test-public-command.py').read_text(encoding='utf-8'))

    def test_guest_ucode_awk_emits_only_fixed_classes_and_public_locations(self):
        private = 'private-key-url-config-fixture'
        guest = (ROOT / 'scripts/test-openwrt-guest.sh').read_text(encoding='utf-8')
        program = re.search(r"\n    awk '([\s\S]+?)' \"\$TMP/status.checked\"", guest).group(1)
        awk = shutil.which('awk') or (str(pathlib.Path(SH).with_name('awk.exe')) if SH else '')
        if not pathlib.Path(awk).is_file():
            self.skipTest('A native awk is required for safe guest diagnostics')
        commands = [[awk]]
        if shutil.which('busybox'):
            commands.append([shutil.which('busybox'), 'awk'])
        body = ('Syntax error: Unable to compile module ' + private + '\nReference error: ' + private +
                '\nInvalid SSL certificate: ' + private + '\nServer hostname does not match SSL certificate: ' + private + '\nType error: ' + private + '\n  | In /usr/share/csqtt/health.uc, line 1, byte 1:\n' +
                'In function(), file /usr/share/csqtt/runtime.uc, line 2, byte 3:\n' +
                'In /private/policy.uc, line 3, byte 1:\nIn /usr/share/csqtt/policy.uc, line 9999999, byte 1:\n' + private)
        for command in commands:
            result = subprocess.run(command + [program], input=body, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0)
            self.assertNotIn(private, result.stdout)
            self.assertEqual(native_vm.guest_ucode_diagnostics(result.stdout), {
                'classes': ['module_error', 'reference_error', 'syntax_error', 'type_error'],
                'locations': [('health.uc', 1), ('runtime.uc', 2)]})

    def test_guest_ucode_markers_reject_unknown_classes_paths_and_unowned_lines(self):
        private = 'private-key-url-config-fixture'
        body = ('CSQTT_GUEST_UCODE_CLASS=' + private + '\nCSQTT_GUEST_UCODE_CLASS=type_error ' + private +
                '\nCSQTT_GUEST_UCODE_SOURCE=runtime.uc:999999\nCSQTT_GUEST_UCODE_SOURCE=runtime.uc:0\n' +
                'CSQTT_GUEST_UCODE_SOURCE=/private/runtime.uc:1\nCSQTT_GUEST_UCODE_SOURCE=runtime.uc:1 ' + private + '\n')
        self.assertEqual(native_vm.guest_ucode_diagnostics(body), {'classes': [], 'locations': []})
        with tempfile.TemporaryDirectory() as temporary:
            source = pathlib.Path(temporary)
            target = source / 'openwrt/csqtt/files/runtime.uc'
            target.parent.mkdir(parents=True)
            target.write_text('public line\n', encoding='utf-8')
            self.assertEqual(native_vm.guest_ucode_diagnostics(
                'CSQTT_GUEST_UCODE_SOURCE=runtime.uc:2\nCSQTT_GUEST_UCODE_SOURCE=runtime.uc:1\n', source),
                {'classes': [], 'locations': [('runtime.uc', 1)]})

    def test_guest_trace_returns_only_a_source_owned_assertion_before_fail_or_cleanup(self):
        private = 'private-key-url-config-fixture'
        lines = (ROOT / 'scripts/test-openwrt-guest.sh').read_text(encoding='utf-8').splitlines()
        owned = next(n for n, line in enumerate(lines, 1) if line.startswith('ucode "$TMP/import.uc"'))
        other = next(n for n, line in enumerate(lines, 1) if line == 'stage native_imports')
        definition = next(n for n, line in enumerate(lines, 1) if line.startswith('fail()'))
        trace = '+CSQTT_GUEST_TRACE:' + str(owned) + ': fail\n'
        cases = ((trace, owned), (trace.replace('\n', '\r\n'), owned),
                 ('+CSQTT_GUEST_TRACE:' + str(other) + ': fail\n', None),
                 (trace.replace(': fail', ': ' + private), None),
                 (trace.replace(': fail', ': fail ' + private), None),
                 (trace.replace(str(owned), '999999'), None),
                 (trace.replace(str(owned), '0'), None),
                 ('+CSQTT_GUEST_TRACE:' + str(definition) + ': printf ' + private + '\n' + trace, None),
                 ('+CSQTT_GUEST_TRACE:' + str(other) + ': cleanup\n' + trace, None),
                 ('+CSQTT_GUEST_TRACE:' + str(owned) + ': printf ' + private + '\n', None))
        for text, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(native_vm.guest_trace_diagnostics(text), expected)
        self.assertIsNone(native_vm.guest_trace_diagnostics(trace + 'x' * native_vm.DIAGNOSTIC_LIMIT))

    def test_guest_trace_transport_never_prints_trace_values_and_reports_unknown(self):
        private = 'private-key-url-config-fixture'
        source = (ROOT / 'scripts/test-openwrt-guest.sh').read_text(encoding='utf-8').splitlines()
        owned = next(n for n, line in enumerate(source, 1) if line.startswith('ucode "$TMP/import.uc"'))
        for call, expected in (('fail', 'source_line=' + str(owned)), (private, 'unknown')):
            text = '+CSQTT_GUEST_TRACE:' + str(owned) + ': ' + call + '\n' + private + '\n'
            with mock.patch.object(native_vm, 'PHASE', 'native_runtime_dns_firewall_luci'), \
                    mock.patch.object(native_vm.subprocess, 'run', side_effect=[
                        subprocess.CompletedProcess(['ssh'], 1, stdout='', stderr=''),
                        subprocess.CompletedProcess(['ssh'], 0,
                            stdout=(text + '\n' + native_vm.DIAGNOSTIC_READ_OK + '\n').encode(), stderr=b'')]), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(ValueError):
                    native_vm.run_remote(['ssh'], 'false')
            self.assertIn('OpenWrt guest assertion: ' + expected, output.getvalue())
            self.assertNotIn(private, output.getvalue())
            self.assertNotIn('CSQTT_GUEST_TRACE:', output.getvalue())

    @unittest.skipUnless(SH, 'A POSIX shell is required for traced smoke acceptance')
    def test_traced_smoke_requires_success_and_complete_pass_line_before_emitting_fixed_stdout(self):
        grep = shutil.which('grep') or str(pathlib.Path(SH).with_name('grep.exe'))
        if not pathlib.Path(grep).is_file():
            self.skipTest('Native grep is required for the complete marker proof')
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            command = native_vm.guest_smoke_command('/tmp/csqtt-native').replace(
                'cd /tmp/csqtt-native', 'cd ' + shlex.quote(directory.as_posix()))
            script = ('sh() { ' + shlex.quote(pathlib.Path(SH).as_posix()) + ' "$@"; }; grep() { ' +
                      shlex.quote(pathlib.Path(grep).as_posix()) + ' "$@"; }; ' + command)
            for body, accepted in (('echo CSQTT_GUEST_SMOKE_PASS\nexit 0\n', True),
                                   ('echo CSQTT_GUEST_SMOKE_PASS\nexit 1\n', False),
                                   ('echo prefix_CSQTT_GUEST_SMOKE_PASS\nexit 0\n', False)):
                (directory / 'guest.sh').write_text(body, encoding='utf-8')
                result = subprocess.run([SH], input=script, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode == 0, accepted)
                self.assertEqual(result.stdout, 'CSQTT_GUEST_SMOKE_PASS\n' if accepted else '')
                self.assertIn('CSQTT_GUEST_TRACE:', (directory / 'smoke.private.log').read_text())

    def test_platform_probe_trace_classifies_blank_invalid_valid_and_known_family_manager_only(self):
        private = 'private-password-key-url-identity'
        installer = (ROOT / 'install.sh').read_text(encoding='utf-8').splitlines()
        fields = {'CS_PROFILE': 'profile_id', 'CS_ARCH': 'architecture',
                  'CS_FAMILY': 'family', 'CS_PM': 'package_manager'}
        def traced(values):
            lines = []
            for name, field in fields.items():
                assignment = name + '=$(csqtt_j "$CS_TMP/probe.json" \'@.' + field + '\')'
                number = next(number for number, line in enumerate(installer, 1) if assignment in line)
                lines.append('+CSQTT_XTRACE:' + str(number) + ': ' + name + '=' + shlex.quote(values[name]))
            return '\n'.join(lines)
        cases = (({'CS_PROFILE': '', 'CS_ARCH': '', 'CS_FAMILY': '', 'CS_PM': ''},
                  {'CS_PROFILE': 'blank', 'CS_ARCH': 'blank', 'CS_FAMILY': 'blank', 'CS_PM': 'blank'}),
                 ({'CS_PROFILE': 'official-profile', 'CS_ARCH': 'x86_64', 'CS_FAMILY': 'official', 'CS_PM': 'opkg'},
                  {'CS_PROFILE': 'valid', 'CS_ARCH': 'valid', 'CS_FAMILY': 'official', 'CS_PM': 'opkg'}),
                 ({'CS_PROFILE': private + '/invalid', 'CS_ARCH': private + ' invalid',
                   'CS_FAMILY': private, 'CS_PM': private},
                  {'CS_PROFILE': 'invalid', 'CS_ARCH': 'invalid', 'CS_FAMILY': 'unrecognized', 'CS_PM': 'unrecognized'}),
                 ({'CS_PROFILE': '.invalid', 'CS_ARCH': '-invalid', 'CS_FAMILY': 'official', 'CS_PM': 'apk'},
                  {'CS_PROFILE': 'invalid', 'CS_ARCH': 'invalid', 'CS_FAMILY': 'official', 'CS_PM': 'apk'}),
                 ({'CS_PROFILE': 'x' * 201, 'CS_ARCH': 'aarch64_cortex-a53', 'CS_FAMILY': 'official', 'CS_PM': 'apk'},
                  {'CS_PROFILE': 'invalid', 'CS_ARCH': 'valid', 'CS_FAMILY': 'official', 'CS_PM': 'apk'}))
        for values, expected in cases:
            with self.subTest(expected=expected):
                diagnostic = native_vm.installer_diagnostics(traced(values))
                self.assertEqual(diagnostic['platform_trace'], expected)
                self.assertNotIn(private, str(diagnostic))
        values = {'CS_PROFILE': 'official-profile', 'CS_ARCH': 'x86_64', 'CS_FAMILY': 'official', 'CS_PM': 'opkg'}
        trace = traced(values)
        unobserved = {name: 'unobserved' for name in fields}
        for text in (re.sub(r'CSQTT_XTRACE:[0-9]+:', 'CSQTT_XTRACE:1:', trace),
                     trace.replace(': CS_', ': echo CS_'),
                     '+CSQTT_XTRACE:1: csqtt_portable_cleanup\n' + trace):
            self.assertEqual(native_vm.installer_diagnostics(text)['platform_trace'], unobserved)
        # Multiple assignment xtrace formats are accepted only at the source line
        # that contains each individual probe assignment.
        grouped = {}
        for line in trace.splitlines():
            prefix, assignment = line.rsplit(': ', 1)
            grouped.setdefault(prefix, []).append(assignment)
        combined = '\n'.join(prefix + ': ' + ' '.join(assignments) for prefix, assignments in grouped.items())
        self.assertEqual(native_vm.installer_diagnostics(combined)['platform_trace'],
                         {'CS_PROFILE': 'valid', 'CS_ARCH': 'valid', 'CS_FAMILY': 'official', 'CS_PM': 'opkg'})

    def test_platform_probe_trace_public_output_contains_only_fixed_enums(self):
        private = 'private-password-key-url-identity'
        installer = (ROOT / 'install.sh').read_text(encoding='utf-8').splitlines()
        number = next(number for number, line in enumerate(installer, 1)
                      if 'CS_PROFILE=$(csqtt_j "$CS_TMP/probe.json" \'@.profile_id\')' in line)
        trace = '+CSQTT_XTRACE:' + str(number) + ': CS_PROFILE=' + private + '\n'
        sentinel = ('\n' + native_vm.DIAGNOSTIC_READ_OK + '\n').encode('ascii')
        with mock.patch.object(native_vm, 'PHASE', 'bootstrap_and_signature_rejection'), \
                mock.patch.object(native_vm.subprocess, 'run', side_effect=[
                    subprocess.CompletedProcess(['ssh'], 1, stdout='', stderr=''),
                    subprocess.CompletedProcess(['ssh'], 0, stdout=trace.encode('utf-8') + sentinel, stderr=b'')]), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(ValueError):
                native_vm.run_remote(['ssh', 'synthetic-host'], 'false')
        self.assertIn('OpenWrt installer platform trace: CS_PROFILE=valid', output.getvalue())
        self.assertNotIn(private, output.getvalue())

    @unittest.skipUnless(SH, 'A real POSIX shell is required for private xtrace classification')
    def test_real_private_trace_keeps_commands_values_and_cleanup_out_of_public_output(self):
        private = 'private-key-url-configuration-fixture'
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            (directory / 'install.sh').write_text(
                'set -eu\ncsqtt_portable_cleanup() { :; }\n'
                'csqtt_bootstrap() { false; }\n'
                'csqtt_portable_main() { csqtt_bootstrap "$1"; }\n'
                'trap csqtt_portable_cleanup EXIT\ncsqtt_portable_main "' + private + '"\n', encoding='utf-8')
            script = 'sh() { ' + shlex.quote(pathlib.Path(SH).as_posix()) + ' "$@"; }; ' + native_vm.PRIVATE_TRACE
            traced = subprocess.run([SH], input=script, cwd=directory, encoding='utf-8',
                                    capture_output=True, timeout=10)
        self.assertNotEqual(traced.returncode, 0)
        self.assertIn(private, traced.stderr)
        self.assertIn('CSQTT_XTRACE:', traced.stderr)
        classified = native_vm.installer_diagnostics(traced.stderr)
        self.assertEqual(classified['trace_functions'], ['csqtt_portable_main', 'csqtt_bootstrap'])
        self.assertNotIn(private, str(classified))
        self.assertNotIn('csqtt_portable_cleanup', str(classified))
        with mock.patch.object(native_vm, 'PHASE', 'first_offline_install'), \
                mock.patch.object(native_vm.subprocess, 'run', side_effect=[
                    subprocess.CompletedProcess(['ssh'], 1, stdout='', stderr=''),
                    subprocess.CompletedProcess(['ssh'], 0, stdout=(traced.stderr + '\n' +
                                                native_vm.DIAGNOSTIC_READ_OK + '\n').encode('utf-8'), stderr=b'')]), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(ValueError):
                native_vm.run_remote(['ssh', 'synthetic-host'], 'false')
        self.assertIn('OpenWrt installer trace function: csqtt_bootstrap', output.getvalue())
        self.assertNotIn(private, output.getvalue())
        self.assertNotIn('false', output.getvalue())

    def test_private_log_reader_selects_exactly_the_current_phase_or_refuses(self):
        for phase, name in native_vm.PRIVATE_PHASE_LOGS.items():
            with self.subTest(phase=phase), mock.patch.object(native_vm, 'PHASE', phase):
                command = native_vm.private_log_read_command()
            self.assertEqual(re.findall(r'/tmp/csqtt-native/[a-z]+\.private\.log', command),
                             ['/tmp/csqtt-native/' + name + '.private.log'])
            self.assertNotIn('tail', command)
            self.assertIn('count=8192', command)
        with mock.patch.object(native_vm, 'PHASE', 'host_preflight'):
            self.assertEqual(native_vm.private_log_read_command(), 'exit 1')

    @unittest.skipUnless(SH, 'A real POSIX shell is required for private log read failure propagation')
    def test_reader_requires_byte_count_and_read_success_without_implicit_errexit(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            (directory / 'install.private.log').write_text('private-log-fixture', encoding='utf-8')
            with mock.patch.object(native_vm, 'PHASE', 'first_offline_install'):
                command = native_vm.private_log_read_command()
            command = command.replace('/tmp/csqtt-native/', shlex.quote(directory.as_posix()) + '/')
            fixtures = (
                ('wc() { return 1; }; dd() { printf unexpected-read; }; ', False),
                ('wc() { printf "not-a-number\\n"; }; dd() { printf unexpected-read; }; ', False),
                ('wc() { printf "1 2\\n"; }; dd() { printf unexpected-read; }; ', False),
                ('wc() { printf "19\\n"; }; dd() { printf partial-private-log; return 1; }; ', True),
            )
            for functions, partial in fixtures:
                with self.subTest(functions=functions):
                    result = subprocess.run([SH], input=functions + command, encoding='utf-8',
                                            capture_output=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(native_vm.DIAGNOSTIC_READ_OK, result.stdout)
                self.assertNotIn('unexpected-read', result.stdout)
                self.assertEqual('partial-private-log' in result.stdout, partial)

    @unittest.skipUnless(SH, 'A real POSIX shell is required for bounded wc/dd private log reading')
    def test_checked_baseline_reader_is_bounded_and_fails_for_missing_log_or_read_tool(self):
        tools = {}
        for name in ('wc', 'dd'):
            path = shutil.which(name) or str(pathlib.Path(SH).with_name(name + '.exe'))
            if not pathlib.Path(path).is_file():
                self.skipTest('Actual bounded reader requires native wc/dd; Linux CI exercises both')
            tools[name] = pathlib.Path(path).as_posix()
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            with mock.patch.object(native_vm, 'PHASE', 'first_offline_install'):
                command = native_vm.private_log_read_command()
            command = command.replace('/tmp/csqtt-native/', shlex.quote(directory.as_posix()) + '/')
            def run(prefix=''):
                aliases = ''.join(name + '() { ' + shlex.quote(path) + ' "$@"; }; ' for name, path in tools.items())
                script = aliases + prefix + command
                return subprocess.run([SH], input=script, encoding='utf-8', capture_output=True, timeout=10)
            missing = run()
            self.assertNotEqual(missing.returncode, 0)
            log = directory / 'install.private.log'
            content = 'private-early-value' + 'x' * (1024 * 1024) + '\nCSQTT: fixed-last-message\n'
            log.write_text(content, encoding='utf-8')
            result = run()
            self.assertEqual(result.returncode, 0)
            self.assertTrue(result.stdout.endswith('\n' + native_vm.DIAGNOSTIC_READ_OK + '\n'))
            self.assertLessEqual(len(result.stdout.encode('utf-8')),
                                 native_vm.DIAGNOSTIC_LIMIT + len(native_vm.DIAGNOSTIC_READ_OK) + 2)
            self.assertNotIn('private-early-value', result.stdout)
            self.assertIn('fixed-last-message', result.stdout)
            failed_tool = run('dd() { return 1; }; ')
            self.assertNotEqual(failed_tool.returncode, 0)
            self.assertNotIn(native_vm.DIAGNOSTIC_READ_OK, failed_tool.stdout)

    def test_failed_diagnostic_transport_is_reported_without_raw_stderr_or_partial_log(self):
        private = 'private-error-value'
        raw = private.encode('ascii')
        sentinel = ('\n' + native_vm.DIAGNOSTIC_READ_OK + '\n').encode('ascii')
        failures = (subprocess.CompletedProcess(['ssh'], 1, stdout=raw, stderr=raw),
                    subprocess.CompletedProcess(['ssh'], 0, stdout=raw, stderr=raw),
                    subprocess.CompletedProcess(['ssh'], 1, stdout=raw + sentinel, stderr=raw),
                    subprocess.CompletedProcess(['ssh'], 0, stdout=raw * native_vm.DIAGNOSTIC_LIMIT + sentinel,
                                                stderr=raw),
                    subprocess.TimeoutExpired(private, 15))
        for failure in failures:
            responses = [subprocess.CompletedProcess(['ssh'], 1, stdout='', stderr=''), failure]
            with self.subTest(failure=type(failure).__name__), \
                    mock.patch.object(native_vm.subprocess, 'run', side_effect=responses), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(ValueError):
                    native_vm.run_remote(['ssh', 'synthetic-host'], 'false')
            self.assertIn('diagnostic_unavailable', output.getvalue())
            self.assertNotIn(private, output.getvalue())

    def test_exact_bounded_byte_read_can_start_inside_utf8_without_false_unavailable(self):
        marker = b'\ninstall.sh: line 561: private-value: parameter not set\n'
        payload = b'\x80' + b'x' * (native_vm.DIAGNOSTIC_LIMIT - 1 - len(marker)) + marker
        self.assertEqual(len(payload), native_vm.DIAGNOSTIC_LIMIT)
        self.assertGreater(len(payload.decode('utf-8', errors='replace').encode('utf-8')),
                           native_vm.DIAGNOSTIC_LIMIT)
        sentinel = ('\n' + native_vm.DIAGNOSTIC_READ_OK + '\n').encode('ascii')
        def transport(args, **options):
            if options.get('text'):
                return subprocess.CompletedProcess(args, 1, stdout='', stderr='')
            self.assertNotIn('encoding', options)
            self.assertNotIn('errors', options)
            return subprocess.CompletedProcess(args, 0, stdout=payload + sentinel, stderr=b'')
        with mock.patch.object(native_vm, 'PHASE', 'first_offline_install'), \
                mock.patch.object(native_vm.subprocess, 'run', side_effect=transport), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(ValueError):
                native_vm.run_remote(['ssh', 'synthetic-host'], 'false')
        self.assertIn('bounded_read_ok', output.getvalue())
        self.assertNotIn('diagnostic_unavailable', output.getvalue())
        self.assertIn('generated_line=561', output.getvalue())
        self.assertNotIn('private-value', output.getvalue())
        self.assertNotIn('\ufffd', output.getvalue())

    def test_shell_locations_expose_only_valid_generated_line_numbers(self):
        text = '/private/password/install.sh: line 561: secret: parameter not set\n' \
               'install.sh: 23: secret\ninstall.sh: line 99999: secret\n'
        classified = native_vm.installer_diagnostics(text)
        self.assertEqual(classified['generated_error_lines'], [23, 561])
        self.assertNotIn('password', str(classified))
        self.assertNotIn('secret', str(classified))

    def test_private_installer_errors_map_only_complete_static_literals_to_source_lines(self):
        private = 'private-secret-command-url-fixture'
        source = (ROOT / 'scripts/portable-install.sh').read_text(encoding='utf-8').splitlines()
        literal = 'Не удалось прочитать исходный состав пакетов'
        lines = [number for number, line in enumerate(source, 1)
                 if "csqtt_portable_die '" + literal + "'" in line]
        self.assertTrue(lines)
        diagnostic = native_vm.installer_diagnostics('CSQTT: ' + literal + '\n' + private)
        self.assertEqual(diagnostic['portable_error_lines'], lines)
        self.assertNotIn(private, str(diagnostic))
        for text in (literal, 'CSQTT: ' + literal + ' ' + private,
                     'CSQTT: ' + literal + '\n' + 'x' * 40960):
            self.assertEqual(native_vm.installer_diagnostics(text)['portable_error_lines'], [])

    def test_private_missing_tools_and_shell_errors_emit_only_fixed_allowlisted_values(self):
        private = 'private-secret-fixture'
        text = ('CSQTT: В прошивке отсутствует необходимая команда: tar\n'
                'install.sh: line 98: mktemp: not found\n'
                'CSQTT: В прошивке отсутствует необходимая команда: ' + private + '\n'
                'install.sh: line 55: ' + private + ': not found\n'
                'install.sh: ' + private + ': parameter not set\n')
        diagnostic = native_vm.installer_diagnostics(text)
        self.assertEqual(set(diagnostic['missing_tools']), {'tar', 'mktemp'})
        self.assertEqual(diagnostic['shell_errors'], ['unset_parameter'])
        self.assertNotIn(private, str(diagnostic))

    def test_remote_failure_diagnostics_read_only_current_fixed_log_and_do_not_expose_values(self):
        private = 'private-secret-command-url-fixture'
        commands = []
        def transport(args, **options):
            commands.append(args[-1])
            if len(commands) == 1:
                self.assertTrue(options['text'])
                return subprocess.CompletedProcess(args, 1, stdout='', stderr=private)
            self.assertNotIn('text', options)
            self.assertNotIn('encoding', options)
            self.assertNotIn('errors', options)
            return subprocess.CompletedProcess(args, 0,
                    stdout=('CSQTT: В прошивке отсутствует необходимая команда: tar\n' +
                           'CSQTT_GUEST_STAGE=' + private.replace('-', '_') + '\n' + private + '\n' +
                           native_vm.DIAGNOSTIC_READ_OK + '\n').encode('utf-8'),
                    stderr=b'')
        with mock.patch.object(native_vm, 'PHASE', 'first_offline_install'), \
                mock.patch.object(native_vm.subprocess, 'run', side_effect=transport), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(ValueError):
                native_vm.run_remote(['ssh', 'synthetic-host'], 'false')
        self.assertIn('OpenWrt missing tool: tar', output.getvalue())
        self.assertNotIn(private, output.getvalue())
        self.assertNotIn(private.replace('-', '_'), output.getvalue())
        self.assertIn('/install.private.log', commands[1])
        self.assertNotIn('/reject.private.log', commands[1])
        self.assertNotIn('/*.private.log', commands[1])
        self.assertNotIn('tail -c', commands[1])

    def test_guest_missing_tool_marker_emits_only_complete_source_known_names(self):
        private = 'private-secret-command-url-fixture'
        cases = (('nslookup', 'nslookup'), ('nslookup\r', 'nslookup'),
                 (private, None), ('nslookup_suffix', None), ('nslookup ' + private, None),
                 ('nslookup; ' + private, None), ('/private/nslookup', None), ('timeout', None))
        for value, expected in cases:
            body = 'CSQTT_GUEST_MISSING_TOOL=' + value + '\n'
            with self.subTest(value=value), mock.patch.object(native_vm, 'PHASE', 'native_runtime_dns_firewall_luci'), \
                    mock.patch.object(native_vm.subprocess, 'run', side_effect=[
                        subprocess.CompletedProcess(['ssh'], 1, stdout='', stderr=''),
                        subprocess.CompletedProcess(['ssh'], 0, stdout=(body + '\n' +
                            native_vm.DIAGNOSTIC_READ_OK + '\n').encode('utf-8'), stderr=b'')]), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(ValueError):
                    native_vm.run_remote(['ssh', 'synthetic-host'], 'false')
            emitted = [line for line in output.getvalue().splitlines() if line.startswith('OpenWrt guest missing tool:')]
            self.assertEqual(emitted, ['OpenWrt guest missing tool: ' + expected] if expected else [])
            self.assertNotIn(private, output.getvalue())

    @unittest.skipUnless(SH, 'A real POSIX shell is required for exact signature rejection evidence')
    def test_signature_rejection_requires_the_actual_fixed_error_and_nonzero_exit(self):
        rejected = subprocess.CompletedProcess(['synthetic-installer'], 1)
        grep = shutil.which('grep') or str(pathlib.Path(SH).with_name('grep.exe'))
        if not pathlib.Path(grep).is_file():
            self.skipTest('A native grep is required for the actual fixed-message proof')
        with tempfile.TemporaryDirectory() as temporary:
            directory = pathlib.Path(temporary)
            def remote(command):
                command = command.replace('cd /tmp/csqtt-native', 'cd ' + shlex.quote(directory.as_posix()))
                script = ('set -eu; sha256sum() { return 0; }; grep() { ' +
                          shlex.quote(pathlib.Path(grep).as_posix()) + ' "$@"; }; ' + command)
                return subprocess.run([SH], input=script, encoding='utf-8', capture_output=True, check=True)
            for error in ('', 'CSQTT: Missing prerequisite', native_vm.SIGNATURE_REJECTION + ' extra'):
                (directory / 'reject.private.log').write_text(error + '\n', encoding='utf-8')
                with self.assertRaises(subprocess.CalledProcessError):
                    native_vm.require_signature_rejection(remote, rejected)
            (directory / 'reject.private.log').write_text(native_vm.SIGNATURE_REJECTION + '\n', encoding='utf-8')
            native_vm.require_signature_rejection(remote, rejected)
            with self.assertRaises(ValueError):
                native_vm.require_signature_rejection(remote, subprocess.CompletedProcess(['synthetic'], 0))

    def test_boot_signals_report_fixed_categories_without_console_content(self):
        private = 'private-key-command-url-fixture'
        console = ('GRUB Linux version 6.6 OpenWrt 24.10.8\n'
                   'VFS: Mounted root (ext4 filesystem)\n'
                   'Waiting for root device PARTUUID=private-value\n'
                   'Kernel panic - not syncing: private-value\n'
                   'Boot failed: No bootable device\n' + vm_console.ACTIVATION + '\n' +
                   vm_console.ROOT_MARKER + NONCE + '\r\r\n' + private + '\n' + vm_console.READY + NONCE + '\r\r\n' +
                   vm_console.STEP_OK + NONCE + '\n' + vm_console.STEP_FAIL + NONCE + '\n')
        signals = vm_console.boot_signals(console)
        self.assertEqual(set(signals), {name for name, pattern in vm_console.SIGNALS})
        self.assertNotIn(private, ','.join(signals))
        self.assertEqual(vm_console.boot_signals(console.encode()), signals)
        self.assertEqual(vm_console.boot_signals(None), ['no_output'])
        self.assertEqual(vm_console.boot_signals('opaque ' + private), ['unclassified_output'])

    def test_boot_signal_scan_is_bounded_to_last_64_kib(self):
        for value in ('Kernel panic ' + 'x' * vm_console.CONSOLE_LIMIT,
                      b'GRUB ' + b'x' * vm_console.CONSOLE_LIMIT,
                      'Linux version ' + '\u0430' * vm_console.CONSOLE_LIMIT):
            self.assertEqual(vm_console.boot_signals(value), ['unclassified_output'])
        self.assertEqual(vm_console.boot_signals('x' * vm_console.CONSOLE_LIMIT + '\nGRUB'), ['grub'])

    def test_console_boot_retains_handshake_command_and_distinct_phases(self):
        guest, phases = mock.Mock(), []
        guest.expect.return_value = 0
        private = 'ssh-ed25519 public-key-fixture'
        with mock.patch.object(vm_console.secrets, 'token_hex', return_value=NONCE) as nonce_source, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            vm_console.prepare_guest_console(guest, private, phases.append, timeout_error=ConsoleTimeout)
        self.assertEqual(nonce_source.call_args_list, [mock.call(16)] * 6)
        self.assertEqual(phases, ['boot_activation_wait', 'boot_console_activate',
                                 'boot_root_check', 'boot_root_check_wait', *STEP_PHASES])
        root_pattern = r'(?m)^' + vm_console.ROOT_MARKER + NONCE + r'\r*$'
        ready_pattern = r'(?m)^' + vm_console.READY + NONCE + r'\r*$'
        ok_pattern = r'(?m)^' + vm_console.STEP_OK + NONCE + r'\r*$'
        fail_pattern = r'(?m)^' + vm_console.STEP_FAIL + NONCE + r'\r*$'
        self.assertEqual(guest.expect.call_args_list,
                         [mock.call(vm_console.ACTIVATION), mock.call(root_pattern, timeout=2),
                          *[mock.call([ok_pattern, fail_pattern], timeout=90) for _ in range(4)],
                          mock.call([ready_pattern, fail_pattern], timeout=90)])
        self.assertEqual(guest.sendline.call_args_list[0], mock.call(''))
        root_command = guest.sendline.call_args_list[1].args[0]
        self.assertTrue(root_command.startswith('test "$(id -u)" = 0 && printf'))
        self.assertNotIn(vm_console.ROOT_MARKER + NONCE, root_command)
        commands = [call.args[0] for call in guest.sendline.call_args_list[2:]]
        self.assertIn('while [ "$(uci -q get network.lan 2>/dev/null)" != interface ]', commands[0])
        command = commands[1]
        self.assertIn("printf '%s\\n' '" + private + "' > /etc/dropbear/authorized_keys", command)
        self.assertIn('&& chmod 600 /etc/dropbear/authorized_keys', command)
        self.assertIn('uci set network.lan.proto=dhcp && uci commit network', commands[2])
        self.assertIn('/etc/init.d/dropbear restart', commands[3])
        self.assertIn('/etc/init.d/network restart', commands[4])
        for command in commands:
            self.assertTrue(command.startswith('if test "$(id -u)" = 0 && ('))
            self.assertNotIn('stty', command)
            self.assertNotIn(vm_console.READY + NONCE, command)
            self.assertNotIn(vm_console.STEP_FAIL + NONCE, command)
        self.assertEqual(output.getvalue(), '')

    def test_root_probe_recovers_two_lost_inputs_before_any_provisioning(self):
        clock, phases = [0.0], []
        class FakeGuest:
            before = 'OpenWrt 24.10.8'
            def __init__(self):
                self.commands, self.root_waits, self.provision_waits = [], 0, 0
            def sendline(self, command):
                self.commands.append(command)
                if len(self.commands) > 4:
                    self_test.assertEqual(self.root_waits, 3)
            def expect(self, pattern, **options):
                if pattern == vm_console.ACTIVATION:
                    return 0
                if isinstance(pattern, list):
                    self.provision_waits += 1
                    return 0
                self.root_waits += 1
                self_test.assertEqual(options['timeout'], 2)
                if self.root_waits <= 2:
                    clock[0] += options['timeout']
                    raise ConsoleTimeout('lost askfirst input')
                self_test.assertRegex('\n' + vm_console.ROOT_MARKER + NONCE + '\r\n', pattern)
                return 0
        self_test, guest = self, FakeGuest()
        with mock.patch.object(vm_console.time, 'monotonic', side_effect=lambda: clock[0]), \
                mock.patch.object(vm_console.secrets, 'token_hex', return_value=NONCE) as nonce_source:
            vm_console.prepare_guest_console(guest, 'key-fixture', phases.append, timeout_error=ConsoleTimeout)
        self.assertEqual(guest.commands[0], '')
        self.assertEqual(guest.commands[1:4], [guest.commands[1]] * 3)
        self.assertTrue(guest.commands[1].startswith('test "$(id -u)" = 0 && printf'))
        self.assertNotIn(vm_console.ROOT_MARKER + NONCE, guest.commands[1])
        self.assertEqual(guest.provision_waits, 5)
        self.assertEqual(nonce_source.call_args_list, [mock.call(16)] * 6)
        self.assertEqual(phases, ['boot_activation_wait', 'boot_console_activate',
                                 'boot_root_check', 'boot_root_check_wait', *STEP_PHASES])

    def test_readonly_probe_deadline_and_attempt_cap_bound_all_timeouts(self):
        for send_delay, wait_advance, expected_attempts, last_window in (
                (0, 0, 90, 2), (0, None, 90, 2), (179.5, None, 1, 0.5)):
            clock, windows, commands = [0.0], [], []
            class FakeGuest:
                def sendline(self, command):
                    commands.append(command)
                    clock[0] += send_delay
                def expect(self, pattern, *, timeout):
                    windows.append(timeout)
                    clock[0] += timeout if wait_advance is None else wait_advance
                    raise ConsoleTimeout('private-timeout-fixture')
            with self.subTest(send_delay=send_delay, wait_advance=wait_advance), \
                    mock.patch.object(vm_console.time, 'monotonic', side_effect=lambda: clock[0]):
                with self.assertRaises(ConsoleTimeout):
                    vm_console._root_shell(FakeGuest(), lambda stage: None, ConsoleTimeout)
            self.assertEqual(len(commands), expected_attempts)
            self.assertEqual(len(windows), expected_attempts)
            self.assertTrue(all(0 < window <= 2 for window in windows))
            self.assertEqual(windows[-1], last_window)
            self.assertLessEqual(clock[0], 180)
            self.assertTrue(all(command.startswith('test "$(id -u)" = 0 && printf') for command in commands))

    def test_root_probe_does_not_retry_eof_or_unrelated_exceptions(self):
        for error in (EOFError('private-eof'), ValueError('private-error'), TimeoutError('other-timeout')):
            guest = mock.Mock()
            guest.before = 'OpenWrt 24.10.8'
            guest.expect.side_effect = [0, error]
            with self.subTest(error=type(error).__name__), contextlib.redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(type(error)) as raised:
                    vm_console.prepare_guest_console(guest, 'private-key', lambda stage: None,
                                                     timeout_error=ConsoleTimeout)
            self.assertIs(raised.exception, error)
            self.assertEqual(guest.sendline.call_count, 2)
            self.assertEqual(guest.expect.call_count, 2)
            self.assertNotIn('private', output.getvalue())

    def test_root_retries_cannot_accept_echo_stale_partial_or_nonroot_output(self):
        for mode in ('echo', 'stale', 'partial', 'nonroot'):
            commands = []
            class FakeGuest:
                before = 'OpenWrt 24.10.8'
                def sendline(self, command):
                    commands.append(command)
                def expect(self, pattern, **options):
                    if pattern == vm_console.ACTIVATION:
                        return 0
                    self_test.assertIsInstance(pattern, str)
                    self.before = {'echo': commands[-1] + '\r\n',
                                   'stale': '\n' + vm_console.ROOT_MARKER + 'b' * 32 + '\r\n',
                                   'partial': '\n' + vm_console.ROOT_MARKER + NONCE[:-1] + '\r\n',
                                   'nonroot': '\nuid=65534\r\n'}[mode]
                    self_test.assertNotRegex(self.before, pattern)
                    raise ConsoleTimeout('private-rejected-marker')
            self_test = self
            with self.subTest(mode=mode), mock.patch.object(vm_console.time, 'monotonic', return_value=0), \
                    mock.patch.object(vm_console.secrets, 'token_hex', return_value=NONCE), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(ConsoleTimeout):
                    vm_console.prepare_guest_console(FakeGuest(), 'private-key', lambda stage: None,
                                                     timeout_error=ConsoleTimeout)
            self.assertEqual(len(commands), 91)
            self.assertTrue(all(command.startswith('test "$(id -u)" = 0 && printf') for command in commands[1:]))
            self.assertNotIn('private', output.getvalue())
            self.assertNotIn(NONCE, output.getvalue())

    @unittest.skipUnless(SH, 'A real POSIX shell is required for prompt-separated result markers')
    def test_all_result_markers_start_a_new_line_after_a_prompt_without_newline(self):
        guest = mock.Mock()
        guest.expect.return_value = 0
        with mock.patch.object(vm_console.secrets, 'token_hex', return_value=NONCE):
            vm_console._root_shell(guest, lambda stage: None, ConsoleTimeout)
        fixtures = [(guest.sendline.call_args.args[0], guest.expect.call_args.args[0])]
        for ready, body, expected_index in ((False, 'true', 0), (False, 'false', 1),
                                            (True, 'true', 0), (True, 'false', 1)):
            guest = mock.Mock()
            guest.expect.return_value = expected_index
            with mock.patch.object(vm_console.secrets, 'token_hex', return_value=NONCE):
                if expected_index:
                    with self.assertRaises(ValueError):
                        vm_console._console_step(guest, lambda stage: None, 'synthetic_step', body, ready=ready)
                else:
                    vm_console._console_step(guest, lambda stage: None, 'synthetic_step', body, ready=ready)
            fixtures.append((guest.sendline.call_args.args[0], guest.expect.call_args.args[0][expected_index]))
        for command, pattern in fixtures:
            with self.subTest(pattern=pattern):
                script = 'id() { printf "0\\n"; }; printf "%s" "root@custom:/# "; ' + command
                result = subprocess.run([SH], input=script, encoding='utf-8', capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0)
                self.assertRegex(result.stdout, pattern)
                self.assertNotRegex('root@custom:/# ' + command, pattern)

    def test_each_console_wait_failure_reports_only_fixed_signals_and_reraises(self):
        for failed_wait, stage in enumerate(('boot_activation_wait', 'boot_root_check_wait', *STEP_PHASES)):
            guest, phases = mock.Mock(), []
            private = 'private-console-command-key-https-fixture'
            guest.before = 'Linux version 6.6 ' + private
            error = TimeoutError(private)
            guest.expect.side_effect = [0] * failed_wait + [error]
            with self.subTest(stage=stage), contextlib.redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(TimeoutError) as raised:
                    vm_console.prepare_guest_console(guest, private, phases.append, timeout_error=ConsoleTimeout)
            self.assertIs(raised.exception, error)
            self.assertEqual(phases[-1], stage)
            self.assertEqual(output.getvalue(), 'OpenWrt VM boot signals: linux\n')
            self.assertNotIn(private, output.getvalue())
            self.assertEqual(guest.sendline.call_count, 0 if failed_wait == 0 else failed_wait + 1)

    def test_only_fresh_marker_output_matches_regardless_of_hostname_and_ansi_prompt(self):
        guest, phases, public_key = mock.Mock(), [], 'ssh-ed25519 key-fixture'
        waits = 0
        def expect(pattern, **options):
            nonlocal waits
            waits += 1
            if waits == 1:
                return 0
            command = guest.sendline.call_args.args[0]
            echoed = '\x1b[32mroot@different-host:/#\x1b[0m ' + command + '\r\n'
            patterns = pattern if isinstance(pattern, list) else [pattern]
            prefixes = ([vm_console.ROOT_MARKER] if waits == 2 else
                        [vm_console.READY if waits == 7 else vm_console.STEP_OK, vm_console.STEP_FAIL])
            for check, prefix in zip(patterns, prefixes):
                self.assertIsNone(re.search(check, echoed), 'Echoed command masqueraded as execution')
                for wrong in (prefix + 'b' * 32 + '\r\n', 'prefix-' + prefix + NONCE + '\r\n',
                              prefix + NONCE + '-suffix\r\n'):
                    self.assertIsNone(re.search(check, wrong))
                for ending in ('\n', '\r\n', '\r\r\n'):
                    self.assertIsNotNone(re.search(check, echoed + prefix + NONCE + ending))
            return 0
        guest.expect.side_effect = expect
        with mock.patch.object(vm_console.secrets, 'token_hex', return_value=NONCE):
            vm_console.prepare_guest_console(guest, public_key, phases.append, timeout_error=ConsoleTimeout)
        self.assertEqual(phases[-1], 'boot_network_restart')

    def test_echo_only_root_check_cannot_trigger_provisioning(self):
        guest, phases = mock.Mock(), []
        private = 'private-echo-command-fixture'
        def expect(pattern, **options):
            if pattern == vm_console.ACTIVATION:
                return 0
            guest.before = guest.sendline.call_args.args[0] + '\r\n' + private
            self.assertIsNone(re.search(pattern, guest.before))
            raise TimeoutError(private)
        guest.expect.side_effect = expect
        with mock.patch.object(vm_console.secrets, 'token_hex', return_value=NONCE), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(TimeoutError):
                vm_console.prepare_guest_console(guest, private, phases.append, timeout_error=ConsoleTimeout)
        self.assertEqual(phases[-1], 'boot_root_check_wait')
        self.assertEqual(guest.sendline.call_count, 2)
        self.assertNotIn(private, output.getvalue())
        self.assertNotIn(NONCE, output.getvalue())

    @unittest.skipUnless(SH, 'A real POSIX shell is required for the UID0/errexit contract')
    def test_uid0_and_successful_provision_are_required_for_marker_output(self):
        guest = mock.Mock()
        guest.expect.return_value = 0
        with mock.patch.object(vm_console.secrets, 'token_hex', return_value=NONCE):
            vm_console.prepare_guest_console(guest, 'key-fixture', lambda stage: None, timeout_error=ConsoleTimeout)
        root_command = guest.sendline.call_args_list[1].args[0]
        root_pattern = guest.expect.call_args_list[1].args[0]
        for uid in (0, 65534):
            command = 'id() { printf "%s\\n" ' + str(uid) + '; }; ' + root_command
            result = subprocess.run([SH, '-c', command], capture_output=True, text=True)
            self.assertEqual(bool(re.search(root_pattern, result.stdout)), uid == 0)
            self.assertEqual(result.returncode, 0 if uid == 0 else 1)
        # Execute the real per-step wrapper with harmless bodies only. Failure
        # must produce its fresh fixed FAIL marker while keeping the shell alive.
        for uid, body, success in ((0, 'true', True), (65534, 'true', False),
                                   (0, 'false && printf should-not-run', False)):
            guest = mock.Mock()
            guest.expect.return_value = 0
            with mock.patch.object(vm_console.secrets, 'token_hex', return_value=NONCE):
                vm_console._console_step(guest, lambda stage: None, 'synthetic_step', body)
            command = 'id() { printf "%s\\n" ' + str(uid) + '; }; ' + guest.sendline.call_args.args[0]
            result = subprocess.run([SH, '-c', command], capture_output=True, text=True, check=True)
            ok, fail = guest.expect.call_args.args[0]
            self.assertEqual(bool(re.search(ok, result.stdout)), success)
            self.assertEqual(bool(re.search(fail, result.stdout)), not success)
            self.assertNotIn('should-not-run', result.stdout)

    def test_each_explicit_step_failure_stops_without_proceeding_and_keeps_diagnostics_safe(self):
        for index, stage in enumerate(STEP_PHASES):
            guest, phases = mock.Mock(), []
            guest.before = vm_console.STEP_FAIL + NONCE + '\r\n'
            guest.expect.side_effect = [0] * (index + 2) + [1]
            with self.subTest(stage=stage), mock.patch.object(vm_console.secrets, 'token_hex', return_value=NONCE), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                with self.assertRaisesRegex(ValueError, 'provisioning step failed'):
                    vm_console.prepare_guest_console(guest, 'private-key-fixture', phases.append,
                                                     timeout_error=ConsoleTimeout)
            self.assertEqual(phases[-1], stage)
            self.assertEqual(guest.sendline.call_count, index + 3)
            self.assertEqual(output.getvalue(), 'OpenWrt VM boot signals: provision_step_failed\n')
            self.assertNotIn(NONCE, output.getvalue())

    @unittest.skipUnless(SH, 'A real POSIX shell is required for the generated network readiness contract')
    def test_generated_lan_must_exist_before_any_network_mutation(self):
        guest = mock.Mock()
        guest.expect.return_value = 0
        with mock.patch.object(vm_console.secrets, 'token_hex', return_value=NONCE):
            vm_console.prepare_guest_console(guest, 'key-fixture', lambda stage: None, timeout_error=ConsoleTimeout)
        command = guest.sendline.call_args_list[2].args[0]
        ok, fail = guest.expect.call_args_list[2].args[0]
        for network_type in ('interface', 'device', ''):
            script = ('id() { printf "0\\n"; }; sleep() { :; }; '
                      'uci() { [ "$*" = "-q get network.lan" ] || exit 99; '
                      'printf "%s\\n" "' + network_type + '"; }; ' + command)
            result = subprocess.run([SH, '-c', script], capture_output=True, text=True, check=True, timeout=10)
            self.assertEqual(bool(re.search(ok, result.stdout)), network_type == 'interface')
            self.assertEqual(bool(re.search(fail, result.stdout)), network_type != 'interface')

    @unittest.skipUnless(SH, 'A real POSIX shell is required for multi-command failure propagation')
    def test_real_key_and_uci_stages_cannot_mask_the_first_failure(self):
        guest = mock.Mock()
        guest.expect.return_value = 0
        with mock.patch.object(vm_console.secrets, 'token_hex', return_value=NONCE):
            vm_console.prepare_guest_console(guest, 'key-fixture', lambda stage: None, timeout_error=ConsoleTimeout)
        fixtures = (
            (3, 'mkdir() { return 1; }; chmod() { printf "unexpected-later-command\\n"; }; '),
            (4, 'uci() { case "$*" in "-q get network.lan") printf "interface\\n";; '
                '"set network.lan.proto=dhcp") return 1;; *) printf "unexpected-later-command\\n";; esac; }; '),
        )
        for call_index, functions in fixtures:
            # mkdir fails before key writes; UCI is entirely stubbed. None of
            # these actual-shell tests touch host settings, keys or services.
            script = 'id() { printf "0\\n"; }; ' + functions + guest.sendline.call_args_list[call_index].args[0]
            result = subprocess.run([SH, '-c', script], capture_output=True, text=True, check=True, timeout=10)
            ok, fail = guest.expect.call_args_list[call_index].args[0]
            self.assertNotRegex(result.stdout, ok)
            self.assertRegex(result.stdout, fail)
            self.assertNotIn('unexpected-later-command', result.stdout)

    def test_both_drivers_use_shared_console_handshake_inside_guest_cleanup(self):
        for filename in ('test-openwrt-vm.py', 'test-public-command.py'):
            source = (ROOT / 'scripts' / filename).read_text(encoding='utf-8')
            self.assertIn('from vm_console import prepare_guest_console', source)
            self.assertIn('try:\n            prepare_guest_console(guest, public_key, phase, '
                          'timeout_error=pexpect.TIMEOUT)', source)
            self.assertIn('finally:\n            guest.terminate(force=True)\n            guest.close(force=True)', source)

    def test_failure_diagnostics_expose_only_stage_class_and_http_status(self):
        private = 'private-command-url-key-output-fixture'
        errors = [ValueError(private), ModuleNotFoundError(private),
                  subprocess.CalledProcessError(1, private, output=private, stderr=private),
                  urllib.error.HTTPError('https://invalid.example/' + private, 403, private, None, None)]
        with mock.patch.object(native_vm, 'PHASE', 'image_download'):
            for error in errors:
                message = native_vm.failure_message(error)
                self.assertIn('stage=image_download', message)
                self.assertIn('exception=' + type(error).__name__, message)
                self.assertNotIn(private, message)
                self.assertNotIn('https:', message)
                self.assertEqual('http_status=403' in message, isinstance(error, urllib.error.HTTPError))

    @unittest.skipUnless(SH, 'A real POSIX shell is required for the mocked SSH contract')
    def test_failed_intermediate_command_cannot_be_masked_by_successful_tail(self):
        shell = subprocess.run
        command = "false; printf '%s\\n' 'tail-success'"
        control = shell([SH, '-c', command], capture_output=True, text=True, check=True)
        self.assertEqual(control.stdout.strip(), 'tail-success')
        transported = []
        def transport(args, **options):
            self.assertEqual(args[:2], ['ssh', 'synthetic-acceptance-host'])
            if len(transported) == 0:
                result = shell([SH, '-c', args[-1]], **options)
                transported.append(result)
                return result
            return subprocess.CompletedProcess(args, 0, stdout=b'', stderr=b'')
        with mock.patch.object(native_vm.subprocess, 'run', side_effect=transport), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, 'native acceptance was not granted'):
                native_vm.run_remote(['ssh', 'synthetic-acceptance-host'], command)
        self.assertNotEqual(transported[0].returncode, 0)
        self.assertNotIn('tail-success', transported[0].stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
