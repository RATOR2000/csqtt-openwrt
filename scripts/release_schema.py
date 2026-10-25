"""Strict release metadata shared by the producer/verifier (never router code)."""
import hashlib
import json
import re

UPSTREAM = 'amurcanov/csqtt@v2.1.9'
ROLES = {'csqtt', 'csqtt-captcha', 'luci-app-csqtt'}
TOKEN = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.+~-]{0,199}\Z')
HASH = re.compile(r'[0-9a-f]{64}\Z')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def token(value):
    return isinstance(value, str) and TOKEN.fullmatch(value) is not None


def load(path):
    require(path.stat().st_size <= 262144, 'Metadata is too large')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique)


def describe(path, **fields):
    return {**fields, 'name': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'size': path.stat().st_size}


def artifact(entry, root=None):
    require(isinstance(entry, dict) and token(entry.get('name')), 'Invalid artifact filename')
    require(type(entry.get('size')) is int and 0 < entry['size'] <= 67108864, 'Invalid artifact size')
    require(isinstance(entry.get('sha256'), str) and HASH.fullmatch(entry['sha256']), 'Invalid artifact digest')
    if root is not None:
        path = root / entry['name']
        require(path.is_file() and not path.is_symlink(), 'Missing or linked artifact')
        require(path.stat().st_size == entry['size'] and hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256'], 'Package checksum or size mismatch')


def validate(manifest, root=None):
    require(isinstance(manifest, dict) and manifest.get('upstream') == UPSTREAM, 'Unsupported upstream')
    schema = manifest.get('schema')
    require(schema in (1, 2), 'Unsupported manifest schema')
    if schema == 1:
        expected = {'openwrt': '25.12.5', 'target': 'mediatek/filogic', 'architecture': 'aarch64_cortex-a53'}
        require(all(manifest.get(k) == v for k, v in expected.items()), 'Unsupported manifest target')
        fmt = 'apk'
    else:
        require(token(manifest.get('profile_id')), 'Invalid profile ID')
        p = manifest.get('platform', {})
        require(p.get('family') in ('official', 'glinet'), 'Unsupported distribution family')
        require(token(p.get('openwrt')) and token(p.get('architecture')), 'Invalid platform release/architecture')
        require(isinstance(p.get('target'), str) and re.fullmatch(r'[A-Za-z0-9_-]+/[A-Za-z0-9_-]+', p['target']), 'Invalid platform target')
        require((p.get('package_manager'), p.get('package_format')) in (('apk', 'apk'), ('opkg', 'ipk')), 'Invalid package backend')
        if p['family'] == 'glinet':
            require(token(p.get('firmware')) and p.get('board') == 'glinet,gl-mt6000', 'Invalid vendor profile')
        require(manifest.get('backend') in ('fw4-nft', 'legacy-xtables'), 'Invalid firewall backend')
        require(manifest.get('dns_binary') in ('/usr/libexec/csqtt/dnsmasq', '/usr/sbin/dnsmasq'), 'Invalid DNS binary')
        q = manifest.get('qualification', {})
        require(type(q.get('installation')) is bool and type(q.get('activation')) is bool, 'Missing qualification gates')
        if q['installation'] or q['activation']:
            require(isinstance(q.get('evidence'), list) and q['evidence'] and all(token(e) for e in q['evidence']), 'Qualified profile requires acceptance evidence references')
        if q.get('preview') and q.get('reason') != 'private_ci_fixture_only':
            require(q.get('physical_device') is False and re.fullmatch(r'[0-9a-f]{40}', q.get('source_commit', '')), 'Preview requires explicit scope and source binding')
            require(isinstance(q.get('proofs'), list) and len(q['proofs']) >= 2, 'Preview requires ABI and firmware proof artifacts')
            for proof in q['proofs']:
                artifact(proof, root)
            require([p['name'] for p in q['proofs']] == q['evidence'], 'Preview evidence references differ from proof bytes')
        r = manifest.get('requirements', {})
        for key in ('overlay_free_kib', 'tmp_free_kib', 'mem_available_kib'):
            require(type(r.get(key)) is int and 0 < r[key] <= 4194304, 'Invalid resource requirement')
        require(isinstance(r.get('packages'), list) and len(r['packages']) <= 64 and all(token(n) for n in r['packages']), 'Invalid required packages')
        if q['installation']:
            require(token(r.get('kernel_package')), 'Qualified profile requires exact kernel package ABI')
        fmt = p['package_format']
    packages = manifest.get('packages')
    require(isinstance(packages, list) and len(packages) == 3, 'Expected three router packages')
    seen = set()
    all_names = set()
    for package in packages:
        artifact(package, root)
        if schema == 1:
            match = re.fullmatch(r'(csqtt-captcha|luci-app-csqtt|csqtt)-[0-9][A-Za-z0-9_.+~-]*\.apk', package['name'])
            role = match[1] if match else None
        else:
            role = package.get('role')
            require(token(package.get('version')), 'Invalid package version')
            require(package['name'].startswith(manifest['profile_id'] + '--') and package['name'].endswith('.' + fmt), 'Package is not scoped to profile')
        require(role in ROLES and role not in seen, 'Invalid or duplicate package role')
        seen.add(role)
        all_names.add(package['name'])
    if schema == 2:
        bundle = manifest.get('dependency_bundle', {'indexes': [], 'packages': []})
        indexes, deps = bundle.get('indexes'), bundle.get('packages')
        require(isinstance(indexes, list) and len(indexes) <= 16 and isinstance(deps, list) and len(deps) <= 64, 'Invalid dependency bundle')
        by_id = {}
        for index in indexes:
            artifact(index, root)
            require(token(index.get('id')) and index['id'] not in by_id, 'Duplicate dependency index')
            require(index.get('format') == ('apk-adb' if fmt == 'apk' else 'opkg'), 'Dependency index backend mismatch')
            require(HASH.fullmatch(index.get('key_sha256', '')), 'Missing dependency source key pin')
            repository = index.get('repository', '')
            hosts = ('downloads.openwrt.org',) if manifest['platform']['family'] == 'official' else ('fw.gl-inet.com', 'dl.gl-inet.com')
            require(any(repository.startswith('https://' + h + '/') for h in hosts) and re.fullmatch(r'https://[A-Za-z0-9_./+-]+', repository), 'Dependency source is not an allowed distribution feed')
            if fmt == 'ipk':
                artifact(index.get('signature', {}), root)
                all_names.add(index['signature']['name'])
            by_id[index['id']] = index
            all_names.add(index['name'])
        dep_names = set()
        for dep in deps:
            artifact(dep, root)
            require(token(dep.get('package')) and token(dep.get('version')) and token(dep.get('filename')), 'Invalid dependency identity')
            require(dep['package'] not in dep_names and dep['package'] not in ROLES, 'Duplicate dependency package')
            if dep['package'].startswith('kmod-'):
                require(token(r.get('kernel_package')) and dep.get('kernel_package') == r['kernel_package'], 'Kernel module requires exact running kernel ABI')
            else:
                require(dep['package'] not in ('kernel', 'procd', 'netifd') and not dep['package'].startswith(('dnsmasq', 'firewall')), 'Kernel/DNS/firewall/services must come from the running firmware')
            require(dep.get('index') in by_id and dep['filename'].endswith('.' + fmt), 'Dependency index or filename mismatch')
            dep_names.add(dep['package'])
            all_names.add(dep['name'])
        require(len(all_names) == len(packages) + len(indexes) + len(deps) + (len(indexes) if fmt == 'ipk' else 0), 'Duplicate artifact filename')
        sources = manifest.get('third_party_sources', [])
        require(isinstance(sources, list) and len(sources) <= 16, 'Invalid corresponding source artifacts')
        for source in sources:
            artifact(source, root)
            require(source['name'] not in all_names and token(source.get('component')) and token(source.get('license')), 'Invalid corresponding source identity')
            all_names.add(source['name'])
    if root is not None:
        actual = {p.name for p in root.iterdir() if p.suffix in ('.apk', '.ipk')}
        expected = {name for name in all_names if name.endswith(('.apk', '.ipk'))}
        require(actual == expected, 'Package directory differs from manifest')
    return manifest
