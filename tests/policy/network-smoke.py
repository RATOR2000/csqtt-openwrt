#!/usr/bin/env python3
"""Exercise production nft output in isolated namespaces with a simulated csqtt0."""
import os
import pathlib
import re
import select
import subprocess
import sys

out = pathlib.Path(sys.argv[1]).resolve()
prefix = f"csqtt-ci-{os.getpid()}"
names = {name: f"{prefix}-{name}" for name in ("router", "a", "b", "wan", "vpn")}
processes = []
created = []

def run(*args, check=True):
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and result.returncode:
        raise RuntimeError(f"Command failed: {' '.join(args)}\n{result.stderr.strip()}")
    return result

def ns(name, *args, check=True):
    return run("ip", "netns", "exec", names[name], *args, check=check)

def ip(name, *args):
    return ns(name, "ip", *args)

def link(left, right, left_ns, right_ns):
    # Create both ends inside the test namespaces; never claim a host interface.
    ip(left_ns, "link", "add", left, "type", "veth", "peer", "name", right,
       "netns", names[right_ns])
    ip(left_ns, "link", "set", left, "up")
    ip(right_ns, "link", "set", right, "up")

client_code = """import socket,sys
s=socket.socket(socket.AF_INET6 if ':' in sys.argv[1] else socket.AF_INET,socket.SOCK_DGRAM)
s.settimeout(.6)
if len(sys.argv)>2:s.bind((sys.argv[2],0))
try:
 s.connect((sys.argv[1],9123));s.send(b'csqtt-fixture');data=s.recv(100)
 label,sep,payload=data.partition(b':')
 print(label.decode() if sep and payload==b'csqtt-fixture' else 'unexpected')
except OSError: print('blocked')
"""

def expect(client, dest, path, source=None):
    args = (dest,) if source is None else (dest, source)
    result = ns(client, "python3", "-c", client_code, *args).stdout.strip()
    wanted = path or "blocked"
    if result != wanted:
        for namespace, command in (
            ("router", ("ip", "-4", "rule", "show")),
            ("router", ("ip", "-4", "route", "show", "table", "202")),
            ("router", ("ip", "-s", "link", "show", "dev", "csqtt0")),
            ("router", ("nft", "list", "chain", "inet", "csqtt", "forward_guard")),
            ("router", ("nft", "list", "chain", "inet", "csqtt", "nat")),
            ("vpn", ("ip", "-4", "route", "show")),
        ):
            details = ns(namespace, *command, check=False)
            print(f"Diagnostic {namespace}: {' '.join(command)}\n{(details.stdout + details.stderr).strip()[:1600]}", file=sys.stderr)
        raise AssertionError(f"{client} → {dest}: expected {wanted}, got {result}")

def echo_server(namespace, label, addresses):
    code = """import socket,selectors,sys
sel=selectors.DefaultSelector()
for addr in sys.argv[2:]:
 family=socket.AF_INET6 if ':' in addr else socket.AF_INET
 s=socket.socket(family,socket.SOCK_DGRAM)
 if family==socket.AF_INET6:s.setsockopt(socket.IPPROTO_IPV6,socket.IPV6_V6ONLY,1)
 s.bind((addr,9123));sel.register(s,selectors.EVENT_READ)
print('ready',flush=True)
while True:
 for key,_ in sel.select():
  data,peer=key.fileobj.recvfrom(100);key.fileobj.sendto(sys.argv[1].encode()+b':'+data,peer)
"""
    process = subprocess.Popen(["ip", "netns", "exec", names[namespace], "python3", "-c", code, label, *addresses],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    processes.append(process)
    ready, _, _ = select.select([process.stdout], [], [], 5)
    if not ready or process.stdout.readline().strip() != "ready":
        raise RuntimeError(f"Echo server did not start in {namespace}")

def load(name):
    ns("router", "nft", "-c", "-f", str(out / name))
    ns("router", "nft", "-f", str(out / name))

try:
    for name in names.values():
        run("ip", "netns", "add", name)
        created.append(name)
    for name in names:
        ip(name, "link", "set", "lo", "up")
    link("ca", "ra", "a", "router")
    link("cb", "rb", "b", "router")
    link("rw", "sw", "router", "wan")
    link("csqtt0", "sv", "router", "vpn")
    ip("router", "link", "add", "br-lan", "type", "bridge")
    ip("router", "link", "set", "ra", "master", "br-lan")
    ip("router", "link", "set", "rb", "master", "br-lan")
    ip("router", "link", "set", "br-lan", "up")
    ip("router", "addr", "add", "192.168.1.1/24", "dev", "br-lan")
    ip("router", "addr", "add", "10.200.0.1/24", "dev", "rw")
    ip("router", "addr", "add", "198.18.0.1/32", "dev", "lo")
    ip("wan", "addr", "add", "10.200.0.2/24", "dev", "sw")
    ip("router", "addr", "add", "10.66.67.1/24", "dev", "csqtt0")
    ip("vpn", "addr", "add", "10.66.67.2/24", "dev", "sv")
    for destination in ("198.51.100.2/32", "203.0.113.2/32"):
        ip("wan", "addr", "add", destination, "dev", "lo")
        ip("vpn", "addr", "add", destination, "dev", "lo")
    ip("router", "route", "add", "default", "via", "10.200.0.2")
    ip("wan", "route", "add", "192.168.1.0/24", "via", "10.200.0.1")
    for name, iface, number in (("a", "ca", 1), ("b", "cb", 2)):
        ip(name, "link", "set", iface, "address", f"02:00:00:00:00:0{number}")
        ip(name, "addr", "add", f"192.168.1.{10 + number}/24", "dev", iface)
        ip(name, "route", "add", "default", "via", "192.168.1.1")
        ip(name, "-6", "addr", "add", f"fd00:1::{10 + number}/64", "dev", iface, "nodad")
        ip(name, "-6", "route", "add", "default", "via", "fd00:1::1")
    ip("router", "-6", "addr", "add", "fd00:1::1/64", "dev", "br-lan", "nodad")
    ip("router", "-6", "addr", "add", "2001:db8:2::1/64", "dev", "rw", "nodad")
    ip("wan", "-6", "addr", "add", "2001:db8:2::2/64", "dev", "sw", "nodad")
    ip("wan", "-6", "route", "add", "fd00:1::/64", "via", "2001:db8:2::1")
    ip("wan", "-6", "addr", "add", "fd00:2::2/128", "dev", "lo", "nodad")
    ip("router", "-6", "route", "add", "fd00:2::2/128", "via", "2001:db8:2::2")
    ns("router", "sysctl", "-qw", "net.ipv4.ip_forward=1")
    ns("router", "sysctl", "-qw", "net.ipv6.conf.all.forwarding=1")
    # Reverse-path filtering is outside the generated policy contract. Strict
    # mode would reject the simulated VPN reply because main points at WAN.
    ns("router", "sysctl", "-qw", "net.ipv4.conf.all.rp_filter=0", "net.ipv4.conf.default.rp_filter=0")
    for interface in ("lo", "br-lan", "ra", "rb", "rw", "csqtt0"):
        ns("router", "sysctl", "-qw", f"net.ipv4.conf.{interface}.rp_filter=0")
    ip("router", "route", "add", "unreachable", "default", "table", "202", "metric", "42760")
    ip("router", "rule", "add", "pref", "11880", "from", "198.18.0.1/32", "lookup", "202")
    ip("router", "rule", "add", "pref", "11881", "from", "198.18.0.1/32", "unreachable")
    ip("router", "rule", "add", "pref", "11890", "fwmark", "0x40000000/0x60000000", "lookup", "202")
    ip("router", "rule", "add", "pref", "11900", "fwmark", "0x40000000/0x60000000", "unreachable")
    ip("router", "rule", "add", "pref", "11910", "fwmark", "0x20000000/0x60000000", "lookup", "main")
    # A wildcard UDP socket can reply with the egress interface address. That
    # breaks the reverse conntrack tuple after masquerade. Bind each destination
    # so replies retain the requested source address, as a real endpoint would.
    for namespace, addresses in (
        ("wan", ("198.51.100.2", "203.0.113.2", "2001:db8:2::2", "fd00:2::2")),
        ("vpn", ("198.51.100.2", "203.0.113.2")),
        ("router", ("192.168.1.1", "fd00:1::1")),
    ):
        echo_server(namespace, namespace, addresses)
    dns_script = pathlib.Path(__file__).with_name("dns-smoke.py").resolve()
    first_dns = run("python3", str(dns_script), "maintenance", str(out), *(names[name] for name in ("router", "a", "b", "wan", "vpn")))
    print(first_dns.stdout.strip())
    load("native-policy.nft")
    expect("b", "198.51.100.2", "wan")
    expect("a", "203.0.113.2", "wan")
    expect("a", "198.51.100.2", False)
    expect("b", "2001:db8:2::2", False)
    expect("b", "fd00:2::2", False)
    expect("a", "192.168.1.1", "router")
    expect("a", "fd00:1::1", "router")
    expect("router", "198.51.100.2", False, "198.18.0.1")
    # A routed veth is only a simulated tunnel. Distinct echo labels prove the
    # selected path; masquerade provides the VPN sink's return route to LAN.
    ip("router", "route", "add", "default", "via", "10.66.67.2", "dev", "csqtt0",
       "table", "202", "metric", "10")
    expect("a", "198.51.100.2", "vpn")
    expect("a", "203.0.113.2", "wan")
    expect("b", "198.51.100.2", "wan")
    expect("router", "198.51.100.2", "vpn", "198.18.0.1")
    ip("router", "route", "del", "default", "dev", "csqtt0", "table", "202", "metric", "10")
    expect("a", "198.51.100.2", False)
    expect("a", "203.0.113.2", "wan")
    expect("router", "198.51.100.2", False, "198.18.0.1")
    # Guards must still stop fallback when policy routing itself disappears.
    for pref in (11880, 11881, 11890, 11900):
        ip("router", "rule", "del", "pref", str(pref))
    expect("a", "198.51.100.2", False)
    expect("router", "198.51.100.2", False, "198.18.0.1")
    for pref, selector, action in ((11880, ("from", "198.18.0.1/32"), ("lookup", "202")),
                                   (11881, ("from", "198.18.0.1/32"), ("unreachable",)),
                                   (11890, ("fwmark", "0x40000000/0x60000000"), ("lookup", "202")),
                                   (11900, ("fwmark", "0x40000000/0x60000000"), ("unreachable",))):
        ip("router", "rule", "add", "pref", str(pref), *selector, *action)
    sets = re.findall(r"add set inet csqtt (\w+)", (out / "native-policy.nft").read_text())
    wan_domain = next(name for name in sets if name.startswith("d_parent_"))
    vpn_domain = next(name for name in sets if name.startswith("d_protected_domain_"))
    ns("router", "nft", "add", "element", "inet", "csqtt", wan_domain, "{ 198.51.100.2 }")
    expect("a", "198.51.100.2", "wan")
    ns("router", "nft", "add", "element", "inet", "csqtt", vpn_domain, "{ 198.51.100.2 }")
    expect("b", "198.51.100.2", False)
    load("native-policy.nft")  # Reapplying rules must preserve the learned sets.
    expect("a", "198.51.100.2", "wan")
    expect("b", "198.51.100.2", False)
    load("native-hold.nft")
    expect("a", "203.0.113.2", False)
    expect("a", "192.168.1.1", "router")
    expect("a", "fd00:1::1", "router")
    load("native-release.nft")
    expect("a", "203.0.113.2", "wan")
    dns_checks = run("python3", str(dns_script), str(out), *(names[name] for name in ("router", "a", "b", "wan", "vpn")))
    print(dns_checks.stdout.strip())
    ip("b", "link", "set", "cb", "address", "02:00:00:00:00:03")
    ip("router", "neigh", "flush", "dev", "br-lan")
    ip("router", "-6", "neigh", "flush", "dev", "br-lan")
    expect("b", "198.51.100.2", "wan")
    expect("b", "2001:db8:2::2", "wan")
    expect("b", "fd00:2::2", "wan")
    print("Native policy traffic checks passed: simulated VPN/up/down, WAN exceptions, routing loss, guarded source, learned sets/reload, local access, IPv6/ULA")
finally:
    for process in processes:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    for name in reversed(created):
        run("ip", "netns", "delete", name, check=False)
