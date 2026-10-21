#!/usr/bin/env python3
"""Check public files; optionally exercise an isolated existing Mihomo binary."""
import argparse
import copy
import json
import re
import socket
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
REGIONS = ['US', 'TW', 'HK', 'SG']
TERMINAL = 'RouteDeck-Terminal-Reject'
EXPECTED = {
    'openai': ['DOMAIN-SUFFIX,' + d for d in
               ['chatgpt.com', 'openai.com', 'oaistatic.com', 'oaiusercontent.com']],
    'us': ['DOMAIN-SUFFIX,' + d for d in
           ['anthropic.com', 'claude.ai', 'claude.com', 'claudeusercontent.com',
            'google.com', 'googleapis.com', 'gstatic.com', 'googleusercontent.com']],
    'direct': ['DOMAIN,api.deepseek.com'],
}
DOMAIN = re.compile(r'(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\Z')
MIHOMO = None


class UniqueLoader(yaml.SafeLoader):
    pass


def mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if key in result:
            raise ValueError('duplicate YAML key')
        result[key] = loader.construct_object(value_node)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)


def load(path):
    return yaml.load(Path(path).read_text(), Loader=UniqueLoader)


def validate_payload(payload):
    if not isinstance(payload, list) or not payload or len(set(payload)) != len(payload):
        raise ValueError('empty or duplicate rule payload')
    for row in payload:
        parts = row.split(',') if isinstance(row, str) else []
        if len(parts) != 2 or parts[0] not in ('DOMAIN', 'DOMAIN-SUFFIX') or not DOMAIN.fullmatch(parts[1]):
            raise ValueError('invalid domain-only rule')


def validate_names(config, source_payloads=()):
    names = {'DIRECT', 'REJECT', 'REJECT-DROP', 'PASS', 'COMPATIBLE'}
    for obj in config.get('proxies', []) + config.get('proxy-groups', []):
        name = obj.get('name')
        if not isinstance(name, str) or not name or name in names:
            raise ValueError('duplicate or invalid proxy/group name')
        names.add(name)
    # Source prefixes isolate providers. Reject ambiguous names within each source.
    for payload in source_payloads:
        source_names = set()
        for node in payload:
            name = node.get('name')
            if not isinstance(name, str) or not name or name in source_names:
                raise ValueError('duplicate or invalid source node name')
            source_names.add(name)
    return names


class PublicFiles(unittest.TestCase):
    def setUp(self):
        self.config = load(ROOT / 'desktop.yaml')

    def test_rule_contract_and_embedded_first_start_data(self):
        for name, expected in EXPECTED.items():
            payload = load(ROOT / 'rules' / (name + '.yaml'))['payload']
            validate_payload(payload)
            self.assertEqual(payload, expected)
            provider = self.config['rule-providers']['RouteDeck-' + name]
            self.assertEqual(provider['payload'], payload)
            self.assertEqual((provider['type'], provider['behavior'], provider['format'], provider['interval']),
                             ('http', 'classical', 'yaml', 86400))
            self.assertEqual(provider['url'], 'https://raw.githubusercontent.com/NBStarry/RouteDeck-Rules/stable/v1/routing/rules/' + name + '.yaml')
        self.assertEqual(self.config['rules'], [
            'RULE-SET,RouteDeck-openai,RouteDeck-OpenAI', 'RULE-SET,RouteDeck-us,RouteDeck-US',
            'RULE-SET,RouteDeck-direct,DIRECT', 'MATCH,RouteDeck-Proxy'])

    def test_bad_rule_data_and_duplicate_names_rejected(self):
        for payload in ([], ['DOMAIN,bad..example'], ['DOMAIN,a.example,DIRECT'],
                        ['GEOIP,CN'], ['DOMAIN,a.example', 'DOMAIN,a.example']):
            with self.assertRaises(ValueError):
                validate_payload(payload)
        config = copy.deepcopy(self.config)
        config['proxies'] = [{'name': 'RouteDeck-US', 'type': 'reject'}]
        with self.assertRaises(ValueError):
            validate_names(config)
        with self.assertRaises(ValueError):
            validate_names(self.config, [[{'name': 'US-A'}, {'name': 'US-A'}]])
        with self.assertRaises(ValueError):
            yaml.load('payload: []\npayload: []', Loader=UniqueLoader)

    def test_closed_groups_sources_and_cache_paths(self):
        names = validate_names(self.config)
        providers = self.config['proxy-providers']
        self.assertEqual(providers['RouteDeck-Terminal'],
                         {'type': 'inline', 'payload': [{'name': TERMINAL, 'type': 'reject'}]})
        self.assertEqual(len(self.config['proxy-groups']), 6)
        for group in self.config['proxy-groups'][:4]:
            self.assertEqual(group['type'], 'fallback')
            self.assertEqual(group['use'], ['RouteDeck-Source-A', 'RouteDeck-Source-B', 'RouteDeck-Terminal'])
            self.assertNotIn('reject', group['exclude-type'].lower().split('|'))
            self.assertTrue(re.search(group['filter'], TERMINAL))
            self.assertFalse(re.search(group['exclude-filter'], TERMINAL))
            self.assertFalse(any(k.startswith('include-all') for k in group))
        for group in self.config['proxy-groups'][4:]:
            self.assertEqual(group['type'], 'select')
            self.assertEqual(group['proxies'], ['RouteDeck-' + r for r in REGIONS])
            self.assertTrue(set(group['proxies']) <= names)
        caches = [p['path'] for p in list(providers.values()) + list(self.config['rule-providers'].values()) if 'path' in p]
        self.assertEqual(len(caches), len(set(caches)))
        for suffix in ['A', 'B']:
            provider = providers['RouteDeck-Source-' + suffix]
            self.assertTrue(provider['url'].startswith('https://example.invalid/'))
            self.assertEqual(provider['proxy'], 'DIRECT')
            self.assertEqual(provider['override']['additional-prefix'], suffix + ' · ')
        self.assertNotIn('dns', self.config)
        self.assertEqual(self.config['proxies'], [])

    def test_name_boundaries(self):
        for group in self.config['proxy-groups'][:4]:
            region = group['name'].removeprefix('RouteDeck-')
            accepted = lambda name: bool(re.search(group['filter'], name)) and not re.search(group['exclude-filter'], name)
            self.assertTrue(accepted(region + '-node'))
            for bad in ['AUS-node', 'manual-only ' + region, region + ' iKuuu', region + '-HK-TW-US-SG']:
                self.assertFalse(accepted(bad), (region, bad))


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


class Sink(BaseHTTPRequestHandler):
    hits = 0
    def do_GET(self):
        type(self).hits += 1
        self.send_response(204)
        self.end_headers()
    def log_message(self, *args):
        pass


@unittest.skipUnless(MIHOMO, 'pass --mihomo to run the actual core checks')
class NativeCore(unittest.TestCase):
    def test_http_sources_bootstrap_without_cached_nodes(self):
        class Source(BaseHTTPRequestHandler):
            hits = 0
            status = 200
            def do_GET(self):
                type(self).hits += 1
                if self.status != 200:
                    self.send_response(self.status)
                    self.end_headers()
                    return
                body = yaml.safe_dump({'proxies': [{'name': 'US-seed', 'type': 'ss',
                    'server': '127.0.0.1', 'port': 1, 'cipher': 'aes-128-gcm',
                    'password': 'synthetic-only'}]}).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Source)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory(prefix='routedeck-bootstrap-') as folder:
                cfg = load(ROOT / 'desktop.yaml')
                control = free_port()
                cfg.update({'mixed-port': 0, 'external-controller': '127.0.0.1:' + str(control),
                            'allow-lan': False, 'log-level': 'silent', 'dns': {'enable': False}})
                for name in ['A', 'B']:
                    provider = cfg['proxy-providers']['RouteDeck-Source-' + name]
                    provider['url'] = 'http://127.0.0.1:' + str(server.server_port) + '/' + name
                    provider.pop('health-check', None)
                for group in cfg['proxy-groups'][:4]:
                    group.update({'url': 'http://127.0.0.1:1/health', 'interval': 3600})
                for provider in cfg['rule-providers'].values():
                    payload = provider['payload']
                    provider.clear()
                    provider.update({'type': 'inline', 'behavior': 'classical', 'payload': payload})
                path = Path(folder) / 'config.yaml'
                path.write_text(yaml.safe_dump(cfg, allow_unicode=True))
                with open(Path(folder) / 'kernel.log', 'w') as log:
                    process = subprocess.Popen([MIHOMO, '-d', folder, '-f', str(path)], stdout=log, stderr=log)
                    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                    try:
                        for _ in range(100):
                            try:
                                with opener.open('http://127.0.0.1:' + str(control) + '/proxies', timeout=.5) as response:
                                    members = json.load(response)['proxies']['RouteDeck-US']['all']
                                if members == ['A · US-seed', 'B · US-seed', TERMINAL]:
                                    break
                            except (OSError, ValueError, KeyError):
                                pass
                            time.sleep(.05)
                        else:
                            self.fail('source downloads cannot bootstrap without cached nodes')
                        self.assertGreaterEqual(Source.hits, 2)
                        cache = Path(folder) / 'providers/routedeck/v1/source-a.yaml'
                        saved = cache.read_bytes()
                        Source.status = 503
                        request = urllib.request.Request('http://127.0.0.1:' + str(control) +
                            '/providers/proxies/RouteDeck-Source-A', method='PUT')
                        with self.assertRaises(urllib.error.HTTPError):
                            opener.open(request, timeout=3)
                        self.assertEqual(cache.read_bytes(), saved)
                        with opener.open('http://127.0.0.1:' + str(control) + '/proxies', timeout=1) as response:
                            self.assertEqual(json.load(response)['proxies']['RouteDeck-US']['all'], members)
                    finally:
                        process.terminate()
                        process.wait(timeout=5)
        finally:
            server.shutdown()
            server.server_close()

    def test_filtered_members_and_empty_regions_never_direct(self):
        for sample in ['regions', 'group-filter', 'only-hk', 'unclassified']:
            with self.subTest(sample=sample), tempfile.TemporaryDirectory(prefix='routedeck-test-') as folder:
                cfg = load(ROOT / 'desktop.yaml')
                control, mixed = free_port(), free_port()
                cfg.update({'mixed-port': mixed, 'external-controller': '127.0.0.1:' + str(control),
                            'allow-lan': False, 'log-level': 'silent', 'dns': {'enable': False}})
                for rp in cfg['rule-providers'].values():
                    rows = rp['payload']
                    rp.clear()
                    rp.update({'type': 'inline', 'behavior': 'classical', 'payload': rows})
                for group in cfg['proxy-groups'][:4]:
                    group['url'] = 'http://127.0.0.1:1/health'
                    group['interval'] = 3600
                fixtures = REGIONS if sample in ['regions', 'group-filter'] else ['HK'] if sample == 'only-hk' else ['JP']
                for source in ['A', 'B']:
                    nodes = [{'name': r + '-node', 'type': 'ss', 'server': '127.0.0.1', 'port': 1,
                              'cipher': 'aes-128-gcm', 'password': 'synthetic-only'} for r in fixtures]
                    if sample in ['regions', 'group-filter']:
                        nodes += [{'name': n, 'type': 'ss', 'server': '127.0.0.1', 'port': 1,
                                   'cipher': 'aes-128-gcm', 'password': 'synthetic-only'}
                                  for n in ['US-HK', 'manual-only US', 'US iKuuu', 'AUS-node']]
                        nodes += [{'name': 'US-private-' + t, 'type': t, 'server': '127.0.0.1', 'port': 1} for t in ['socks5', 'http', 'direct']]
                        if sample == 'regions':
                            nodes += [{'name': 'US-private-' + t, 'type': t} for t in ['wireguard', 'reject']]
                    provider = cfg['proxy-providers']['RouteDeck-Source-' + source]
                    provider.update({'type': 'inline', 'payload': nodes})
                    if sample == 'group-filter':
                        provider.pop('exclude-type', None)
                    for key in ['url', 'path', 'interval', 'health-check']:
                        provider.pop(key, None)
                path = Path(folder) / 'config.yaml'
                path.write_text(yaml.safe_dump(cfg, allow_unicode=True))
                check = subprocess.run([MIHOMO, '-t', '-d', folder, '-f', str(path)], capture_output=True, timeout=15)
                self.assertEqual(check.returncode, 0, 'synthetic core parsing failed')
                with open(Path(folder) / 'kernel.log', 'w') as log:
                    process = subprocess.Popen([MIHOMO, '-d', folder, '-f', str(path)], stdout=log, stderr=log)
                    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                    try:
                        for _ in range(100):
                            try:
                                with opener.open('http://127.0.0.1:' + str(control) + '/proxies', timeout=.5) as response:
                                    groups = json.load(response)['proxies']
                                break
                            except (OSError, ValueError):
                                time.sleep(.05)
                        else:
                            self.fail('isolated core did not start')
                        for region in REGIONS:
                            expected = [source + ' · ' + region + '-node' for source in ['A', 'B']] if region in fixtures else []
                            self.assertEqual(groups['RouteDeck-' + region]['all'], expected + [TERMINAL])
                        for name in ['OpenAI', 'Proxy']:
                            self.assertEqual(groups['RouteDeck-' + name]['now'], 'RouteDeck-US')
                        if sample in ['only-hk', 'unclassified']:
                            Sink.hits = 0
                            server = ThreadingHTTPServer(('127.0.0.1', 0), Sink)
                            threading.Thread(target=server.serve_forever, daemon=True).start()
                            try:
                                with socket.create_connection(('127.0.0.1', mixed), timeout=2) as client:
                                    client.settimeout(2)
                                    target = 'http://127.0.0.1:' + str(server.server_port) + '/probe'
                                    client.sendall(('GET ' + target + ' HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n').encode())
                                    reply = client.recv(4096)
                                self.assertIn(b'502', reply.split(b'\r\n')[0])
                                self.assertEqual(Sink.hits, 0)
                            finally:
                                server.shutdown()
                                server.server_close()
                    finally:
                        process.terminate()
                        process.wait(timeout=5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mihomo', help='existing native binary; isolated tests use loopback only')
    args = parser.parse_args()
    MIHOMO = args.mihomo
    NativeCore.__unittest_skip__ = not bool(MIHOMO)
    unittest.main(argv=[__file__], verbosity=2)
