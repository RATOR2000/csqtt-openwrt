#!/usr/bin/env python3
"""Real group-dnsmasq queries inside network-smoke's disposable namespaces."""
import json
import os
import pathlib
import select
import socket
import struct
import subprocess
import sys
import time


def question_end(packet, start=12):
    cursor = start
    while cursor < len(packet):
        size = packet[cursor]
        cursor += 1
        if size == 0:
            return cursor
        if size & 0xC0 == 0xC0:
            if cursor >= len(packet):
                raise ValueError("Truncated DNS compression pointer")
            return cursor + 1
        if size > 63 or cursor + size > len(packet):
            raise ValueError("Invalid DNS label")
        cursor += size
    raise ValueError("Truncated DNS name")


def dns_response(packet, address):
    if len(packet) < 12:
        raise ValueError("Truncated DNS header")
    ident, _, questions, _, _, _ = struct.unpack("!6H", packet[:12])
    if questions != 1:
        raise ValueError("Expected one DNS question")
    end = question_end(packet) + 4
    if end > len(packet):
        raise ValueError("Truncated DNS question")
    kind, cls = struct.unpack("!2H", packet[end - 4:end])
    answer = b""
    if kind == 1 and cls == 1:
        answer = b"\xc0\x0c" + struct.pack("!HHIH", 1, 1, 60, 4) + socket.inet_aton(address)
    return struct.pack("!6H", ident, 0x8180, 1, bool(answer), 0, 0) + packet[12:end] + answer


def decode_response(packet, ident):
    if len(packet) < 12:
        raise ValueError("Truncated DNS reply")
    got, flags, questions, answers, _, _ = struct.unpack("!6H", packet[:12])
    if got != ident or not flags & 0x8000 or questions > 16 or answers > 256:
        raise ValueError("Invalid DNS reply header")
    cursor = 12
    for _ in range(questions):
        cursor = question_end(packet, cursor) + 4
    result = []
    for _ in range(answers):
        cursor = question_end(packet, cursor)
        if cursor + 10 > len(packet):
            raise ValueError("Truncated DNS answer")
        kind, cls, _, size = struct.unpack("!HHIH", packet[cursor:cursor + 10])
        cursor += 10
        if cursor + size > len(packet):
            raise ValueError("Truncated DNS answer data")
        if kind == 1 and cls == 1 and size == 4:
            result.append(socket.inet_ntoa(packet[cursor:cursor + 4]))
        cursor += size
    return {"answers": result, "rcode": flags & 15}


def receive(client, size):
    packet = b""
    while len(packet) < size:
        chunk = client.recv(size - len(packet))
        if not chunk:
            raise OSError("Truncated DNS TCP reply")
        packet += chunk
    return packet


def query(name, server="9.9.9.9", port=53, transport="udp"):
    labels = name.encode("ascii").split(b".")
    if any(not label or len(label) > 63 for label in labels):
        raise ValueError("Invalid fixture query")
    ident = int.from_bytes(os.urandom(2), "big")
    packet = struct.pack("!6H", ident, 0x0100, 1, 0, 0, 0)
    packet += b"".join(bytes([len(label)]) + label for label in labels) + b"\0\0\x01\0\x01"
    family = socket.AF_INET6 if ":" in server else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM if transport == "tcp" else socket.SOCK_DGRAM) as client:
        client.settimeout(1.2)
        # An explicitly configured public DNS server must be intercepted into
        # the client's own group listener, including reply address/port NAT.
        try:
            client.connect((server, port))
            if transport == "tcp":
                client.sendall(struct.pack("!H", len(packet)) + packet)
                reply = receive(client, struct.unpack("!H", receive(client, 2))[0])
            else:
                client.send(packet)
                reply = client.recv(4096)
            return decode_response(reply, ident)
        except OSError:
            return {"answers": [], "rcode": None}


def serve(address, binds):
    sockets = []
    for bind in binds:
        for transport in (socket.SOCK_DGRAM, socket.SOCK_STREAM):
            listener = socket.socket(socket.AF_INET, transport)
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((bind, 53))
            if transport == socket.SOCK_STREAM:
                listener.listen(16)
            sockets.append(listener)
    print("ready", flush=True)
    while True:
        ready, _, _ = select.select(sockets, [], [])
        for listener in ready:
            if listener.type == socket.SOCK_STREAM:
                client, _ = listener.accept()
                with client:
                    client.settimeout(2)
                    try:
                        size = struct.unpack("!H", receive(client, 2))[0]
                        if size < 12 or size > 4096:
                            raise ValueError("Invalid DNS TCP query size")
                        response = dns_response(receive(client, size), address)
                        client.sendall(struct.pack("!H", len(response)) + response)
                    except (OSError, ValueError):
                        continue
            else:
                packet, peer = listener.recvfrom(4096)
                try:
                    listener.sendto(dns_response(packet, address), peer)
                except ValueError:
                    continue


def maintenance(out, namespaces):
    """First failed publication: only the saved hold exists, no policy/DNS redirect."""
    script = pathlib.Path(__file__).resolve()
    binary = script.parents[2] / ".work/dnsmasq-2.93/src/dnsmasq"
    processes, configs = [], []
    answer = "93.184.216.101"
    token, counter = os.urandom(4).hex(), 0
    observer = "csqtt_dns_proof"

    def run(namespace, *args, check=True):
        result = subprocess.run(["ip", "netns", "exec", namespaces[namespace], *args],
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        if check and result.returncode:
            raise RuntimeError(f"Maintenance fixture failed: {' '.join(args)}\n{result.stderr.strip()}")
        return result

    def spawn(namespace, *args, ready=False):
        process = subprocess.Popen(["ip", "netns", "exec", namespaces[namespace], *args],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        processes.append(process)
        if ready:
            readable, _, _ = select.select([process.stdout], [], [], 5)
            if not readable or process.stdout.readline().strip() != "ready":
                raise RuntimeError(f"Maintenance listener did not start in {namespace}")
        return process

    def expect(client, port, transport, expected, server="192.168.1.1"):
        nonlocal counter
        counter += 1
        name = f"hold-{token}-{counter}.example.invalid"
        response = json.loads(run(client, "python3", str(script), "query", name, server, str(port), transport).stdout)
        wanted = [] if expected is None else [expected]
        if response["answers"] != wanted or (expected and response["rcode"] != 0):
            raise AssertionError(f"Maintenance {client} {transport} DNS {server}:{port}: expected {wanted}, got {response}")

    def upstream_packets():
        result = json.loads(run("router", "nft", "-j", "list", "chain", "inet", observer, "output").stdout)
        return sum(expr["counter"]["packets"] for entry in result["nftables"] if "rule" in entry
                   for expr in entry["rule"]["expr"] if "counter" in expr)

    try:
        if not binary.is_file():
            raise RuntimeError("Pinned DNS fixture binary is missing")
        if run("router", "nft", "list", "table", "inet", "csqtt", check=False).returncode == 0:
            raise AssertionError("First-activation fixture already has a full policy")
        run("wan", "ip", "addr", "add", "9.9.9.9/32", "dev", "lo")
        spawn("wan", "python3", str(script), "serve", answer, "9.9.9.9", ready=True)
        # Real primary DNS and an old WAN group listener both recurse over WAN.
        # A hold that protects only forwarding would leave both sockets reachable.
        for port in (53, 5400):
            config = out / f"maintenance-dns-{port}.conf"
            configs.append(config)
            config.write_text(f"port={port}\nbind-interfaces\nlisten-address=127.0.0.1,192.168.1.1,fd00:1::1\n"
                              f"no-resolv\nno-hosts\ncache-size=0\nserver=9.9.9.9\nuser=root\npid-file={out / ('maintenance-' + str(port) + '.pid')}\n")
            process = spawn("router", str(binary), "--keep-in-foreground", f"--conf-file={config}", "--log-facility=-")
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f"Maintenance dnsmasq exited: {process.stderr.read()[:1600]}")
                listeners = run("router", "ss", "-H", "-lun").stdout
                if f"192.168.1.1:{port}" in listeners and f"[fd00:1::1]:{port}" in listeners:
                    break
                time.sleep(.05)
            else:
                raise RuntimeError(f"Maintenance dnsmasq did not bind port {port}")
        http = """import socket
s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('192.168.1.1',8080));s.listen()
print('ready',flush=True)
while True:
 c,_=s.accept();c.settimeout(2)
 try:c.recv(4096);c.sendall(b'HTTP/1.0 200 OK\\r\\nContent-Length: 2\\r\\n\\r\\nok')
 except OSError:pass
 finally:c.close()
"""
        spawn("router", "python3", "-c", http, ready=True)
        run("b", "ip", "link", "set", "cb", "address", "02:00:00:00:00:03")
        run("router", "ip", "neigh", "flush", "dev", "br-lan")
        run("router", "ip", "-6", "neigh", "flush", "dev", "br-lan")
        for server in ("192.168.1.1", "fd00:1::1"):
            for port in (53, 5400):
                for transport in ("udp", "tcp"):
                    expect("a", port, transport, answer, server)
                    expect("b", port, transport, answer, server)
        run("router", "nft", "add", "table", "inet", observer)
        run("router", "nft", "add", "chain", "inet", observer, "output",
            "{ type filter hook output priority -5; policy accept; }")
        run("router", "nft", "add", "rule", "inet", observer, "output", "ip daddr 9.9.9.9 meta l4proto { tcp, udp } th dport 53 counter")
        run("router", "nft", "-f", str(out / "native-hold.nft"))
        before = upstream_packets()
        for server in ("192.168.1.1", "fd00:1::1"):
            for port in (53, 5400):
                for transport in ("udp", "tcp"):
                    expect("a", port, transport, None, server)
        if upstream_packets() != before:
            raise AssertionError("Protected maintenance DNS reached the WAN resolver")
        for server in ("192.168.1.1", "fd00:1::1"):
            for port in (53, 5400):
                for transport in ("udp", "tcp"):
                    expect("b", port, transport, answer, server)
        for port in (53, 5400):
            for transport in ("udp", "tcp"):
                expect("router", port, transport, answer, "127.0.0.1")
        expect("router", 53, "udp", answer, "9.9.9.9")
        run("a", "ping", "-c", "1", "-W", "1", "192.168.1.1")
        run("a", "python3", "-c", "import urllib.request; r=urllib.request.urlopen('http://192.168.1.1:8080/',timeout=2); assert r.status==200 and r.read()==b'ok'")
        # One nft transaction empties both forwarding and DNS maintenance chains.
        run("router", "nft", "-f", str(out / "native-release.nft"))
        for port in (53, 5400):
            for transport in ("udp", "tcp"):
                expect("a", port, transport, answer)
        print("Native maintenance DNS checks passed: first activation without full policy, TCP/UDP IPv4/IPv6 input held, zero WAN recursion, old group port, unassigned/loopback/router DNS, LAN ping/HTTP, atomic release")
    finally:
        run("router", "nft", "delete", "table", "inet", observer, check=False)
        run("b", "ip", "link", "set", "cb", "address", "02:00:00:00:00:02", check=False)
        run("router", "ip", "neigh", "flush", "dev", "br-lan", check=False)
        run("router", "ip", "-6", "neigh", "flush", "dev", "br-lan", check=False)
        for process in reversed(processes):
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        run("wan", "ip", "addr", "del", "9.9.9.9/32", "dev", "lo", check=False)
        for config in configs:
            config.unlink(missing_ok=True)


def smoke(out, namespaces):
    script = pathlib.Path(__file__).resolve()
    binary = script.parents[2] / ".work/dnsmasq-2.93/src/dnsmasq"
    processes = []
    dnsmasqs = []
    healthy = False
    counter = 0
    token = os.urandom(4).hex()
    # Documentation ranges are rejected by dnsmasq's real rebind protection.
    # These public answers are produced only by the isolated fixture resolvers;
    # the test never connects to the returned addresses.
    wan_answer, vpn_answer, local_answer = "93.184.216.101", "93.184.216.102", "192.168.1.100"
    ipv6_servers = ("fd00:1::1", "2001:db8:2::2")

    def run(namespace, *args, check=True):
        result = subprocess.run(["ip", "netns", "exec", namespaces[namespace], *args],
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        if check and result.returncode:
            raise RuntimeError(f"DNS fixture command failed: {' '.join(args)}\n{result.stderr.strip()}")
        return result

    def responder(namespace, answer, binds):
        process = subprocess.Popen(["ip", "netns", "exec", namespaces[namespace], "python3", str(script),
                                    "serve", answer, *binds], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        processes.append(process)
        ready, _, _ = select.select([process.stdout], [], [], 5)
        if not ready or process.stdout.readline().strip() != "ready":
            raise RuntimeError(f"DNS responder did not start in {namespace}")

    def expect(client, suffix, answer, server="9.9.9.9"):
        nonlocal counter
        counter += 1
        name = f"q{token}-{counter}" + (f".{suffix}" if suffix else "")
        response = json.loads(run(client, "python3", str(script), "query", name, server).stdout)
        expected = [] if answer is None else [answer]
        if response["answers"] != expected or (answer and response["rcode"] != 0):
            raise AssertionError(f"{client} DNS {name} via {server}: expected {expected}, got {response}")

    def populated(prefix, address):
        model = json.loads((out / "native-model.json").read_text())
        name = next(rule["set"] for rule in model["rules"] if rule["set"].startswith(prefix))
        result = json.loads(run("router", "nft", "-j", "list", "set", "inet", "csqtt", name).stdout)
        entries = next(entry["set"].get("elem", []) for entry in result["nftables"] if "set" in entry)
        if address not in entries:
            raise AssertionError(f"DNS answer {address} missing from {name}: {entries}")

    try:
        if not binary.is_file():
            raise RuntimeError("Pinned DNS fixture binary is missing")
        # Both upstream addresses exist on both paths. Wrong VPN fallback would
        # return the WAN answer, so a missing WAN endpoint cannot hide a leak.
        for namespace, answer in (("wan", wan_answer), ("vpn", vpn_answer)):
            for address in ("1.1.1.1/32", "9.9.9.9/32"):
                run(namespace, "ip", "addr", "add", address, "dev", "lo")
            responder(namespace, answer, ("1.1.1.1", "9.9.9.9"))
        responder("router", local_answer, ("127.0.0.1",))
        for group, port in (("private", 5400), ("direct", 5401)):
            # Copy only into the runner's temp output directory. Keep production
            # upstream/nftset options; only the fixture's PID/log paths change.
            config = (out / f"native-dns-{group}.conf").read_text()
            config = "\n".join(f"pid-file={out / ('dns-' + group + '.pid')}" if line.startswith("pid-file=") else line
                               for line in config.splitlines()) + "\n"
            path = out / f"smoke-dns-{group}.conf"
            path.write_text(config)
            process = subprocess.Popen(["ip", "netns", "exec", namespaces["router"], str(binary),
                                        "--keep-in-foreground", f"--conf-file={path}", "--log-facility=-", "--log-queries"],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            processes.append(process)
            dnsmasqs.append(process)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f"Group dnsmasq {group} exited: {process.stderr.read()[:1600]}")
                if f"192.168.1.1:{port}" in run("router", "ss", "-H", "-lun").stdout:
                    break
                time.sleep(.05)
            else:
                raise RuntimeError(f"Group dnsmasq {group} did not bind the LAN listener")

        expect("a", "example.invalid", None)  # VPN-default, tunnel down.
        expect("a", "example.org", wan_answer)  # Explicit WAN exception.
        populated("d_parent_", wan_answer)
        expect("a", "secure.example.org", wan_answer)  # Earlier parent wins.
        populated("d_parent_", wan_answer)
        populated("d_child_", wan_answer)
        expect("b", "example.invalid", wan_answer)  # WAN-default.
        expect("b", "example.net", None)  # Explicit VPN exception, down.
        expect("a", "lan", local_answer)
        expect("b", "lan", local_answer)
        expect("a", "", local_answer)
        expect("b", "", local_answer)
        # IPv6 client transport must reach the same guarded IPv4 upstreams.
        # Test both the router's LAN address and redirected external DNS.
        for server in ipv6_servers:
            expect("a", "example.invalid", None, server)
            expect("a", "example.org", wan_answer, server)
            expect("b", "example.invalid", wan_answer, server)
            expect("b", "example.net", None, server)
            expect("a", "lan", local_answer, server)
            expect("b", "lan", local_answer, server)
        run("router", "ip", "route", "add", "default", "via", "10.66.67.2", "dev", "csqtt0",
            "table", "202", "metric", "10")
        healthy = True
        expect("a", "example.invalid", vpn_answer)
        expect("b", "example.net", vpn_answer)
        populated("d_protected_domain_", vpn_answer)
        expect("a", "example.org", wan_answer)
        for server in ipv6_servers:
            expect("a", "example.invalid", vpn_answer, server)
            expect("b", "example.net", vpn_answer, server)
        run("router", "ip", "route", "del", "default", "dev", "csqtt0", "table", "202", "metric", "10")
        healthy = False
        expect("a", "example.invalid", None)
        expect("b", "example.net", None)
        expect("a", "example.org", wan_answer)
        for server in ipv6_servers:
            expect("a", "example.invalid", None, server)
            expect("b", "example.net", None, server)
            expect("a", "lan", local_answer, server)
            expect("b", "lan", local_answer, server)
        print("Native DNS traffic checks passed: IPv4/IPv6 transport, guarded defaults/exceptions, exact upstream path, local names, nftset population, tunnel up/down")
    except Exception:
        for process in dnsmasqs:
            process.terminate()
            try:
                _, error = process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                _, error = process.communicate(timeout=2)
            print(f"Group dnsmasq diagnostic:\n{error[-2400:]}", file=sys.stderr)
        raise
    finally:
        if healthy:
            run("router", "ip", "route", "del", "default", "dev", "csqtt0", "table", "202", "metric", "10", check=False)
        for process in reversed(processes):
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)


if __name__ == "__main__":
    if sys.argv[1] == "serve":
        serve(sys.argv[2], sys.argv[3:])
    elif sys.argv[1] == "query":
        print(json.dumps(query(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "9.9.9.9",
                               int(sys.argv[4]) if len(sys.argv) > 4 else 53, sys.argv[5] if len(sys.argv) > 5 else "udp")))
    elif sys.argv[1] == "maintenance":
        maintenance(pathlib.Path(sys.argv[2]).resolve(), dict(zip(("router", "a", "b", "wan", "vpn"), sys.argv[3:])))
    else:
        smoke(pathlib.Path(sys.argv[1]).resolve(), dict(zip(("router", "a", "b", "wan", "vpn"), sys.argv[2:])))
