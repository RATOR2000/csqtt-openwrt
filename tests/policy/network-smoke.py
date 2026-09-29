#!/usr/bin/env python3
"""Exercise production nft output in isolated Linux namespaces, without a VPN."""
import pathlib
import re
import subprocess
import sys
import time

out = pathlib.Path(sys.argv[1]).resolve()
prefix = "csqtt-ci"
names = {name: f"{prefix}-{name}" for name in ("router", "a", "b", "wan")}
processes = []

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
    run("ip", "link", "add", left, "type", "veth", "peer", "name", right)
    run("ip", "link", "set", left, "netns", names[left_ns])
    run("ip", "link", "set", right, "netns", names[right_ns])
    ip(left_ns, "link", "set", left, "up")
    ip(right_ns, "link", "set", right, "up")

client_code = """import socket,sys
s=socket.socket(socket.AF_INET6 if ':' in sys.argv[1] else socket.AF_INET,socket.SOCK_DGRAM)
s.settimeout(.6)
try:
 s.sendto(b'csqtt-fixture',(sys.argv[1],9123)); data,_=s.recvfrom(100)
 print('ok' if data==b'csqtt-fixture' else 'blocked')
except OSError: print('blocked')
"""

def expect(client, dest, allowed):
    result = ns(client, "python3", "-c", client_code, dest).stdout.strip()
    wanted = "ok" if allowed else "blocked"
    if result != wanted:
        raise AssertionError(f"{client} → {dest}: expected {wanted}, got {result}")

def load(name):
    ns("router", "nft", "-c", "-f", str(out / name))
    ns("router", "nft", "-f", str(out / name))

try:
    for name in names.values():
        run("ip", "netns", "add", name)
    for name in names:
        ip(name, "link", "set", "lo", "up")
    link("ca", "ra", "a", "router")
    link("cb", "rb", "b", "router")
    link("rw", "sw", "router", "wan")
    ip("router", "link", "add", "br-lan", "type", "bridge")
    ip("router", "link", "set", "ra", "master", "br-lan")
    ip("router", "link", "set", "rb", "master", "br-lan")
    ip("router", "link", "set", "br-lan", "up")
    ip("router", "addr", "add", "192.168.1.1/24", "dev", "br-lan")
    ip("router", "addr", "add", "10.200.0.1/24", "dev", "rw")
    ip("router", "addr", "add", "198.18.0.1/32", "dev", "lo")
    ip("wan", "addr", "add", "10.200.0.2/24", "dev", "sw")
    for destination in ("198.51.100.2/32", "203.0.113.2/32"):
        ip("wan", "addr", "add", destination, "dev", "lo")
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
    ns("router", "sysctl", "-qw", "net.ipv4.ip_forward=1")
    ns("router", "sysctl", "-qw", "net.ipv6.conf.all.forwarding=1")
    ip("router", "route", "add", "unreachable", "default", "table", "202", "metric", "42760")
    ip("router", "rule", "add", "pref", "11890", "fwmark", "0x40000000/0x60000000", "lookup", "202")
    ip("router", "rule", "add", "pref", "11900", "fwmark", "0x40000000/0x60000000", "unreachable")
    server_code = """import socket,selectors
sel=selectors.DefaultSelector()
for family,addr in ((socket.AF_INET,'0.0.0.0'),(socket.AF_INET6,'::')):
 s=socket.socket(family,socket.SOCK_DGRAM)
 if family==socket.AF_INET6:s.setsockopt(socket.IPPROTO_IPV6,socket.IPV6_V6ONLY,1)
 s.bind((addr,9123));sel.register(s,selectors.EVENT_READ)
while True:
 for key,_ in sel.select():
  data,peer=key.fileobj.recvfrom(100);key.fileobj.sendto(data,peer)
"""
    processes.append(subprocess.Popen(["ip", "netns", "exec", names["wan"], "python3", "-c", server_code]))
    time.sleep(.15)
    load("native-policy.nft")
    expect("b", "198.51.100.2", True)
    expect("a", "203.0.113.2", True)
    expect("a", "198.51.100.2", False)
    expect("b", "2001:db8:2::2", False)
    sets = re.findall(r"add set inet csqtt (\w+)", (out / "native-policy.nft").read_text())
    wan_domain = next(name for name in sets if name.startswith("d_parent_"))
    vpn_domain = next(name for name in sets if name.startswith("d_protected_domain_"))
    ns("router", "nft", "add", "element", "inet", "csqtt", wan_domain, "{ 198.51.100.2 }")
    expect("a", "198.51.100.2", True)
    ns("router", "nft", "add", "element", "inet", "csqtt", vpn_domain, "{ 198.51.100.2 }")
    expect("b", "198.51.100.2", False)
    load("native-policy.nft")  # Reapplying rules must preserve the learned sets.
    expect("a", "198.51.100.2", True)
    expect("b", "198.51.100.2", False)
    load("native-hold.nft")
    expect("a", "203.0.113.2", False)
    load("native-release.nft")
    expect("a", "203.0.113.2", True)
    ip("b", "link", "set", "cb", "address", "02:00:00:00:00:03")
    expect("b", "198.51.100.2", True)
    expect("b", "2001:db8:2::2", True)
    print("Native policy traffic checks passed: direct, exceptions, fail-closed, reload, IPv6")
finally:
    for process in processes:
        process.terminate()
        process.wait(timeout=5)
    for name in reversed(list(names.values())):
        run("ip", "netns", "delete", name, check=False)
