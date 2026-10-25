#!/usr/bin/env python3
"""Real xtables/ipset plus independent nft guards in disposable Linux namespaces.

This proves host-kernel behavior, not GL.iNet's 5.4 kernel or hardware offload.
No command addresses a host interface or the user's router.
"""
import json
import os
import pathlib
import select
import subprocess
import sys

out = pathlib.Path(sys.argv[1]).resolve()
names = {n: f"csqtt-legacy-{os.getpid()}-{n}" for n in ("r", "a", "b", "wan", "vpn")}
created, processes = [], []


def run(*args, check=True, content=None):
    result = subprocess.run(args, input=content, text=True, capture_output=True, timeout=15)
    if check and result.returncode:
        raise RuntimeError(f"Fixture command failed: {' '.join(args)}\n{result.stderr[:1600]}")
    return result


def ns(name, *args, **kwargs):
    return run("ip", "netns", "exec", names[name], *args, **kwargs)


def ip(name, *args):
    return ns(name, "ip", *args)


def spawn(name, *args, ready=True):
    process = subprocess.Popen(["ip", "netns", "exec", names[name], *args], text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    processes.append(process)
    if ready:
        readable, _, _ = select.select([process.stdout], [], [], 5)
        if not readable or process.stdout.readline().strip() != "ready":
            raise RuntimeError(f"Fixture server failed in {name}")
    return process


def link(left, right, a, b):
    ip(a, "link", "add", left, "type", "veth", "peer", "name", right, "netns", names[b])
    ip(a, "link", "set", left, "up")
    ip(b, "link", "set", right, "up")


def restore(family, name, test=False):
    command = "ip6tables-restore" if family == 6 else "iptables-restore"
    ns("r", command, "--wait", "5", "--noflush", *( ["--test"] if test else [] ), content=(out / name).read_text())


def hook(command, table, source, target):
    if ns("r", command, "-w", "5", "-t", table, "-C", source, "-j", target, check=False).returncode:
        ns("r", command, "-w", "5", "-t", table, "-I", source, "1", "-j", target)


def guard(closed):
    file = out / ("legacy-hold.guard.nft" if closed else "legacy-release.guard.nft")
    ns("r", "nft", "-c", "-f", str(file))
    ns("r", "nft", "-f", str(file))


def load_policy():
    ns("r", "ipset", "restore", content=(out / "legacy-policy.ipset").read_text())
    for family in (6, 4):
        restore(family, f"legacy-policy.v{family}", test=True)
        restore(family, f"legacy-policy.v{family}")
    for command, table, source, target in (
        ("iptables", "mangle", "PREROUTING", "CSQ_CLASS"),
        ("iptables", "nat", "PREROUTING", "CSQ_DNS"),
        ("iptables", "nat", "POSTROUTING", "CSQ_NAT"),
        ("iptables", "filter", "FORWARD", "CSQ_FORWARD"),
        ("iptables", "filter", "INPUT", "CSQ_INPUT"),
        ("iptables", "filter", "OUTPUT", "CSQ_OUTPUT"),
        ("ip6tables", "filter", "FORWARD", "CSQ_FORWARD"),
        ("ip6tables", "filter", "INPUT", "CSQ_INPUT"),
    ):
        hook(command, table, source, target)


echo = """import socket,selectors,sys
sel=selectors.DefaultSelector()
for a in sys.argv[2:]:
 s=socket.socket(socket.AF_INET6 if ':' in a else socket.AF_INET,socket.SOCK_DGRAM)
 if ':' in a:s.setsockopt(socket.IPPROTO_IPV6,socket.IPV6_V6ONLY,1)
 s.bind((a,9123));sel.register(s,selectors.EVENT_READ)
print('ready',flush=True)
while True:
 for k,_ in sel.select():
  d,p=k.fileobj.recvfrom(200);k.fileobj.sendto(sys.argv[1].encode()+b':'+d,p)
"""
client = """import socket,sys
s=socket.socket(socket.AF_INET6 if ':' in sys.argv[1] else socket.AF_INET,socket.SOCK_DGRAM);s.settimeout(.6)
if len(sys.argv)>2:s.bind((sys.argv[2],0))
try:
 s.connect((sys.argv[1],9123));s.send(b'legacy-proof');r=s.recv(200)
 print(r.split(b':',1)[0].decode() if r.endswith(b':legacy-proof') else 'invalid')
except OSError:print('blocked')
"""


def expect(name, destination, expected="blocked", source=None):
    result = ns(name, "python3", "-c", client, destination, *([source] if source else [])).stdout.strip()
    if result != expected:
        raise AssertionError(f"{name} to {destination}: expected {expected}, got {result}")


try:
    for name in names.values():
        run("ip", "netns", "add", name)
        created.append(name)
    for name in names:
        ip(name, "link", "set", "lo", "up")
    for left, right, a, b in (("ca", "ra", "a", "r"), ("cb", "rb", "b", "r"),
                              ("rw", "sw", "r", "wan"), ("csqtt0", "sv", "r", "vpn")):
        link(left, right, a, b)
    ip("r", "link", "add", "br-lan", "type", "bridge")
    for interface in ("ra", "rb"):
        ip("r", "link", "set", interface, "master", "br-lan")
    ip("r", "link", "set", "br-lan", "up")
    for name, interface, address in (("r", "br-lan", "192.168.1.1/24"), ("r", "rw", "10.200.0.1/24"),
        ("wan", "sw", "10.200.0.2/24"), ("r", "csqtt0", "10.66.67.1/24"), ("vpn", "sv", "10.66.67.2/24"),
        ("r", "lo", "198.18.0.1/32")):
        ip(name, "addr", "add", address, "dev", interface)
    for name in ("wan", "vpn"):
        for address in ("198.51.100.2/32", "203.0.113.2/32"):
            ip(name, "addr", "add", address, "dev", "lo")
    ip("r", "route", "add", "default", "via", "10.200.0.2")
    ip("wan", "route", "add", "192.168.1.0/24", "via", "10.200.0.1")
    for index, name, interface in ((1, "a", "ca"), (2, "b", "cb")):
        ip(name, "link", "set", interface, "address", f"02:00:00:00:00:0{index}")
        ip(name, "addr", "add", f"192.168.1.{10+index}/24", "dev", interface)
        ip(name, "route", "add", "default", "via", "192.168.1.1")
        ip(name, "-6", "addr", "add", f"fd00:1::{10+index}/64", "dev", interface, "nodad")
        ip(name, "-6", "route", "add", "default", "via", "fd00:1::1")
    for name, interface, address in (("r", "br-lan", "fd00:1::1/64"),
                                    ("r", "rw", "2001:db8:2::1/64"), ("wan", "sw", "2001:db8:2::2/64")):
        ip(name, "-6", "addr", "add", address, "dev", interface, "nodad")
    ip("wan", "-6", "route", "add", "fd00:1::/64", "via", "2001:db8:2::1")
    ns("r", "sysctl", "-qw", "net.ipv4.ip_forward=1", "net.ipv6.conf.all.forwarding=1",
       "net.ipv4.conf.all.rp_filter=0", "net.ipv4.conf.default.rp_filter=0")
    for interface in ("lo", "br-lan", "ra", "rb", "rw", "csqtt0"):
        ns("r", "sysctl", "-qw", f"net.ipv4.conf.{interface}.rp_filter=0")
    ip("r", "route", "add", "unreachable", "default", "table", "202", "metric", "42760")
    for pref, selectors in ((11880, ["from", "198.18.0.1/32", "lookup", "202"]),
        (11881, ["from", "198.18.0.1/32", "unreachable"]),
        (11890, ["fwmark", "0x40000000/0x60000000", "lookup", "202"]),
        (11900, ["fwmark", "0x40000000/0x60000000", "unreachable"]),
        (11910, ["fwmark", "0x20000000/0x60000000", "lookup", "main"])):
        ip("r", "rule", "add", "pref", str(pref), *selectors)
    for name, addresses in (("r", ["192.168.1.1", "fd00:1::1"]),
                            ("wan", ["198.51.100.2", "203.0.113.2", "2001:db8:2::2"]),
                            ("vpn", ["198.51.100.2", "203.0.113.2"])):
        spawn(name, "python3", "-c", echo, name, *addresses)
    guard(True)
    expect("a", "203.0.113.2")
    expect("a", "192.168.1.1", "r")
    expect("a", "fd00:1::1", "r")
    load_policy()
    guard(False)
    expect("a", "198.51.100.2")
    expect("a", "203.0.113.2", "wan")
    expect("b", "198.51.100.2", "wan")
    expect("b", "2001:db8:2::2")
    expect("r", "198.51.100.2", source="198.18.0.1")
    ip("r", "route", "add", "default", "via", "10.66.67.2", "dev", "csqtt0", "table", "202", "metric", "10")
    expect("a", "198.51.100.2", "vpn")
    expect("r", "198.51.100.2", "vpn", source="198.18.0.1")
    # Learned domain sets survive idempotent restoration.
    mappings = {}
    for row in (out / "legacy-dns-private.conf").read_text().splitlines():
        if row.startswith("ipset=/"):
            _, domain, targets = row.split("/")
            mappings[domain] = targets.split(",")
    ns("r", "ipset", "add", mappings["example.org"][0], "198.51.100.2")
    expect("a", "198.51.100.2", "wan")
    load_policy()
    expect("a", "198.51.100.2", "wan")
    # Simulate a failing vendor flush/reload removing every owned xtables
    # rule and policy route. The independent nft table must retain protection.
    for command in ("iptables", "ip6tables"):
        for table in (("filter", "mangle", "nat") if command == "iptables" else ("filter",)):
            ns("r", command, "-w", "5", "-t", table, "-F")
    for pref in (11880, 11881, 11890, 11900):
        ip("r", "rule", "del", "pref", str(pref))
    expect("a", "198.51.100.2")
    expect("a", "203.0.113.2")
    expect("r", "198.51.100.2", source="198.18.0.1")
    expect("a", "192.168.1.1", "r")
    expect("a", "fd00:1::1", "r")
    expect("b", "2001:db8:2::2")
    # Real DNS packets to a WAN-recursing router listener remain blocked after
    # redirect loss, including an old group listener and IPv6 router DNS.
    dns = pathlib.Path(__file__).with_name("dns-smoke.py")
    spawn("r", "python3", str(dns), "serve", "93.184.216.9", "192.168.1.1")
    response = json.loads(ns("a", "python3", str(dns), "query", "lost-redirect.example.invalid", "192.168.1.1", "53", "udp").stdout)
    assert response["answers"] == [], "Unredirected assigned DNS escaped after firewall flush"
    response = json.loads(ns("r", "python3", str(dns), "query", "local-router.example.invalid", "192.168.1.1", "53", "udp").stdout)
    assert response["answers"] == ["93.184.216.9"], "Router-origin DNS must remain available"
    guard(True)
    for family in (4, 6):
        restore(family, f"legacy-hold.v{family}", test=True)
        restore(family, f"legacy-hold.v{family}")
        restore(family, f"legacy-release.v{family}", test=True)
    print("Native legacy namespace proof passed: xtables restore/test, ipset retention, VPN/WAN/local/IPv6/source guards, independent guard survives vendor flush and route loss, DNS hold")
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
