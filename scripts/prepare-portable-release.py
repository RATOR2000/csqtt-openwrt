#!/usr/bin/env python3
"""Promote exact passing candidates into one signed, reviewable release directory."""
import argparse
import json
import pathlib
import shutil
import subprocess
import sys

from release_schema import artifact, describe, load, require, validate

ROOT = pathlib.Path(__file__).resolve().parents[1]


def command(script, *args):
    subprocess.run([sys.executable, str(ROOT / 'scripts' / script), *map(str, args)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=pathlib.Path)
    parser.add_argument('output', type=pathlib.Path)
    args = parser.parse_args()
    require(not args.output.exists(), 'Publication directory must be new')
    manifests = sorted(args.inputs.glob('candidate-*/*-manifest.json'))
    expected = {'official-' + v + '-' + abi for v in ('24.10.8', '25.12.5', '25.12.6')
                for abi in ('mediatek-filogic-aarch64_cortex-a53', 'x86-64-x86_64')}
    require({p.name.removesuffix('-manifest.json') for p in manifests} == expected,
            'All six exact official tuples, including original r9 upgrade ABI, must pass')
    qualified = []
    for path in manifests:
        manifest = validate(load(path), path.parent)
        version = manifest['platform']['openwrt']
        proofs = list((args.inputs / ('native-vm-' + version)).glob('*-vm-evidence.json'))
        require(len(proofs) == 1, 'Missing or ambiguous native firmware VM evidence')
        backend = args.inputs / ('candidate-official-' + version + '-x86-64-x86_64') / ('official-' + version + '-x86-64-x86_64-manifest.json')
        migration = []
        if manifest['profile_id'] == 'official-25.12.5-mediatek-filogic-aarch64_cortex-a53':
            migration = ['--migration-evidence', path.parent / (manifest['profile_id'] + '-migration-evidence.json')]
        command('release-evidence.py', 'qualify', '--directory', path.parent, '--profile', manifest['profile_id'],
                '--vm-evidence', proofs[0], '--backend-manifest', backend, *migration)
        qualified.append(path)
    # Sign exact final manifest bytes before their hashes enter the catalogue.
    command('sign-portable-release.py', args.inputs)
    command('release-catalogue.py', args.inputs, *qualified, '--require-qualified')
    command('sign-portable-release.py', args.inputs, '--catalogue-only')
    args.output.mkdir(parents=True)
    for path in qualified:
        m = validate(load(path), path.parent)
        files = [*m['packages'], *m['dependency_bundle']['packages'], *m['dependency_bundle']['indexes'],
                 *m['qualification']['proofs'], *m.get('third_party_sources', []), describe(path), describe(path.with_suffix('.sig'))]
        files.extend(i['signature'] for i in m['dependency_bundle']['indexes'] if 'signature' in i)
        for entry in files:
            artifact(entry, path.parent)
            destination = args.output / entry['name']
            if destination.exists():
                require(destination.read_bytes() == (path.parent / entry['name']).read_bytes(), 'Different assets share one filename')
            else:
                shutil.copyfile(path.parent / entry['name'], destination)
    for name in ('catalogue.json', 'catalogue.sig'):
        shutil.copyfile(args.inputs / name, args.output / name)
    shutil.copyfile(ROOT / 'install.sh', args.output / 'install.sh')
    shutil.copyfile(ROOT / 'release/csqtt-public.pem', args.output / 'csqtt-public.pem')
    command('sign-portable-release.py', args.output, '--verify-only')
    notes = ('Экспериментальный CSQTT для официальной OpenWrt: установка одной командой и мастер настройки в LuCI. '
             'Установщик выбирает подписанный комплект, проверяет совместимость, устанавливает зависимости и сохраняет настройки. '
             'Штатные DHCP/DNS остаются на месте; для CSQTT используется отдельный DNS-процесс.\n\n'
             'Выполните по SSH на роутере:\n\n```sh\n'
             'uclient-fetch -O /tmp/csqtt-install.sh https://github.com/RATOR2000/csqtt-openwrt/releases/download/v0.1.0-preview.10/install.sh && sh /tmp/csqtt-install.sh v0.1.0-preview.10\n```\n\n'
             'После установки откройте адрес, который напечатает установщик: «Службы → CSQTT». '
             'Мастер объяснит ввод данных и выбор устройств. VPN включается после завершения мастера; начальный профиль — девять соединений. '
             'При обновлении заполненные настройки сохраняются. Неизвестная прошивка или ABI получает безопасный отказ.\n\n'
             'Проверки выпуска: чистые OpenWrt в VM — подписи, установка зависимостей, повторная установка, сохранение настроек, DNS/firewall/LuCI; '
             'параметры стендов — 768МиБ RAM, два CPU, корневой раздел1ГиБ (расширение только временного диска записано в доказательства). '
             'для каждого ABI — ELF, запуск выбранного CPU в эмуляции, Linux TUN и DNS/TLS. '
             'Исходный ARM r9 дополнительно проверен настоящим APK в изолированной базе: подписанные r9 → r10 → r9, без запуска пакетных скриптов. '
             'Это не проверка физических роутеров, реального VK/Android или длительной эксплуатации. '
             'Сохранена совместимость с протоколом amurcanov/csqtt v2.1.9.\n\n'
             'Проверенные сочетания версии, target и ABI (без ограничения моделью):\n\n' +
             ''.join('- `' + load(p)['profile_id'] + '`\n' for p in qualified))
    (args.output / 'RELEASE_NOTES.md').write_text(notes, encoding='utf-8')
    sums = ''.join(f"{describe(p)['sha256']}  {p.name}\n" for p in sorted(args.output.iterdir()) if p.is_file())
    (args.output / 'SHA256SUMS').write_text(sums, encoding='ascii')
    print('Signed official preview assets assembled; existing releases were not changed.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit('Release assembly refused: ' + str(error)) from None
