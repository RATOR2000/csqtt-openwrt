#!/usr/bin/env python3
"""Create or resume an explicitly identified unpublished preview draft only."""
import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess


def run(args):
    return subprocess.run(args, text=True, capture_output=True)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def publish(directory, tag, revision, source, previous='', repository='RATOR2000/csqtt-openwrt', invoke=run):
    require(re.fullmatch(r'v0\.1\.0-preview\.([0-9]+)', tag) and
            tag == 'v0.1.0-preview.' + revision and revision.isdigit() and int(revision) >= 10,
            'Frozen or inconsistent preview tag')
    require(re.fullmatch('[0-9a-f]{40}', source) and
            (not previous or re.fullmatch('[0-9a-f]{40}', previous)), 'Exact source commits required')
    require(repository == 'RATOR2000/csqtt-openwrt', 'Unexpected release repository')
    directory = pathlib.Path(directory)
    files = sorted(directory.iterdir())
    require(files and all(p.is_file() and not p.is_symlink() and
                         re.fullmatch('[A-Za-z0-9][A-Za-z0-9._+-]*', p.name) for p in files),
            'Only flat regular publication files are allowed')
    require({'catalogue.json', 'catalogue.sig', 'install.sh', 'SHA256SUMS', 'RELEASE_NOTES.md'} <=
            {p.name for p in files}, 'Incomplete publication directory')
    hashes = {p.name: ('sha256:' + hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_size) for p in files}

    def changed_files(metadata):
        assets = {a['name']: a for a in metadata.get('assets', [])}
        return [p for p in files if (assets.get(p.name, {}).get('digest'),
                                    assets.get(p.name, {}).get('size')) != hashes[p.name]]

    def checked(args):
        result = invoke(args)
        require(result.returncode == 0, 'GitHub draft operation failed: ' + args[1])
        return result.stdout

    def no_tag():
        result = invoke(['git', 'ls-remote', '--exit-code', '--tags', 'origin', 'refs/tags/' + tag])
        require(result.returncode == 2 and not result.stdout.strip(), 'An existing tag must remain immutable')

    no_tag()
    releases = json.loads(checked(['gh', 'api', 'repos/' + repository + '/releases?per_page=100']))
    require(isinstance(releases, list), 'Invalid release metadata')
    matches = [r for r in releases if r.get('tag_name') == tag]
    require(len(matches) <= 1, 'Ambiguous release draft')
    title = 'CSQTT ' + tag + ' - official OpenWrt preview'
    notes = str(directory / 'RELEASE_NOTES.md')
    if matches:
        old = matches[0]
        require(old.get('draft') is True and old.get('target_commitish') in
                ({source, previous} if previous else {source}), 'Existing release is not this authorized unpublished draft')
        # Recheck immediately before replacing unpublished assets. Published tags
        # and releases never enter this recovery path; prior artifacts stay in CI.
        latest = json.loads(checked(['gh', 'api', 'repos/' + repository + '/releases/' + str(old['id'])]))
        require(latest.get('draft') is True and latest.get('tag_name') == tag and
                latest.get('target_commitish') == old['target_commitish'],
                'Draft changed before upload')
        no_tag()
        changed = changed_files(latest)
        if changed:
            checked(['gh', 'release', 'upload', tag, '--clobber', *map(str, changed)])
        latest = json.loads(checked(['gh', 'api', 'repos/' + repository + '/releases/' + str(old['id'])]))
        require(latest.get('draft') is True and latest.get('tag_name') == tag and
                latest.get('target_commitish') == old['target_commitish'], 'Draft changed during upload')
        require(not changed_files(latest), 'Uploaded draft asset digests do not match verified publication files')
        no_tag()
        checked(['gh', 'release', 'edit', tag, '--target', source, '--draft=true', '--prerelease',
                 '--title', title, '--notes-file', notes])
    else:
        checked(['gh', 'release', 'create', tag, *map(str, files), '--target', source,
                 '--draft', '--prerelease', '--title', title, '--notes-file', notes])
    print('Unpublished preview draft prepared; published tags/releases were not modified.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=pathlib.Path)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--previous-draft-source', default='')
    args = parser.parse_args()
    try:
        publish(args.directory, args.tag, args.revision, os.environ.get('GITHUB_SHA', ''), args.previous_draft_source)
    except (ValueError, OSError, KeyError, json.JSONDecodeError):
        raise SystemExit('Draft publication refused; inspect public workflow checks. No diagnostic secrets printed.') from None
