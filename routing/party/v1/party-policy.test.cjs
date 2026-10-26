const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');
const source = fs.readFileSync(__dirname + '/party-policy.js', 'utf8');
const clone = (value) => JSON.parse(JSON.stringify(value));
const local = () => ({version: 1, allowCurrentProfile: true, excludeNodeNames: [], privateRules: [], privateProxies: [], privateGroups: []});
const node = (name) => ({name, type: 'ss', server: '127.0.0.1', port: 1, cipher: 'aes-128-gcm', password: 'synthetic'});
const fixture = () => ({proxies: ['US one', 'TW one', 'HK one', 'SG one'].map(node), 'x-routedeck-local': local()});
const run = (input) => clone(vm.runInNewContext(source + '\nmain(input)', {input}, {timeout: 1000}));
const group = (out, name) => out['proxy-groups'].find((g) => g.name === 'RouteDeck-' + name);

test('four independent regional fallback chains, terminal last, both selectors default US', () => {
  const out = run(fixture());
  for (const region of ['US', 'TW', 'HK', 'SG']) {
    assert.equal(group(out, region).type, 'fallback');
    assert.deepEqual(group(out, region).proxies, [region + ' one', 'RouteDeck-Terminal-Reject']);
  }
  assert.deepEqual(group(out, 'OpenAI').proxies, ['RouteDeck-US', 'RouteDeck-TW', 'RouteDeck-HK', 'RouteDeck-SG']);
  assert.deepEqual(group(out, 'OpenAI').proxies, group(out, 'Proxy').proxies);
  assert.equal(out.proxies.at(-1).type, 'reject');
});
test('empty US and all-empty inputs keep US default and only terminal rejection', () => {
  for (const proxies of [[node('HK only')], []]) {
    const input = fixture(); input.proxies = proxies;
    const out = run(input);
    assert.deepEqual(group(out, 'US').proxies, ['RouteDeck-Terminal-Reject']);
    assert.equal(group(out, 'Proxy').proxies[0], 'RouteDeck-US');
  }
});
test('private closure and DNS preserved, supplier strategy and marker discarded, input unchanged', () => {
  const input = fixture(); const prepared = input['x-routedeck-local'];
  prepared.privateProxies = [{name: 'local-exit', type: 'socks5', server: '127.0.0.1', port: 1099}];
  prepared.privateGroups = [{name: 'local-group', type: 'select', proxies: ['local-exit']}];
  prepared.privateRules = ['IP-CIDR,100.64.0.0/10,DIRECT,no-resolve', 'DOMAIN,internal.invalid,local-group'];
  prepared.dns = {enable: true, 'enhanced-mode': 'fake-ip'}; prepared.hosts = {'internal.invalid': '127.0.0.1'};
  input.rules = ['MATCH,DIRECT']; input.dns = {nameserver: ['supplier.invalid']};
  input['proxy-groups'] = [{name: 'supplier', type: 'select', proxies: ['DIRECT']}];
  input['proxy-providers'] = {}; input['external-controller'] = '0.0.0.0:9999';
  const before = clone(input); const out = run(input);
  assert.deepEqual(input, before);
  assert.deepEqual(out.rules.slice(0, 2), prepared.privateRules);
  assert.equal(out.rules.at(-1), 'MATCH,RouteDeck-Proxy');
  assert.equal(out.rules.filter((r) => r.startsWith('MATCH,')).length, 1);
  assert.deepEqual(out.dns, prepared.dns); assert.deepEqual(out.hosts, prepared.hosts);
  assert.equal(out['x-routedeck-local'], undefined); assert.equal(out['external-controller'], undefined);
  assert(!out['proxy-groups'].some((g) => g.name === 'supplier'));
  assert(!group(out, 'US').proxies.includes('local-exit'));
});
test('native DNS ownership removes supplier DNS and hosts', () => {
  const input = fixture(); input.dns = {enable: true}; input.hosts = {bad: '127.0.0.1'};
  const out = run(input); assert.equal(out.dns, undefined); assert.equal(out.hosts, undefined);
});
test('manual-only, iKuuu, explicit exclusions and other regions never enter candidates', () => {
  const input = fixture(); input.proxies.push(node('US manual-only'), node('US iKuuu'), node('US excluded'), node('JP other'));
  input['x-routedeck-local'].excludeNodeNames = ['US excluded'];
  assert.deepEqual(group(run(input), 'US').proxies, ['US one', 'RouteDeck-Terminal-Reject']);
});
test('source authorization and required local fields are explicit', () => {
  for (const mutate of [x => delete x['x-routedeck-local'], x => x['x-routedeck-local'].version = 2, x => x['x-routedeck-local'].allowCurrentProfile = false, x => delete x['x-routedeck-local'].excludeNodeNames]) {
    const x = fixture(); mutate(x); assert.throws(() => run(x), /local/);
  }
});
test('trusted preparation replaces supplier marker rather than merging it', () => {
  const input = fixture(); input['x-routedeck-local'] = {version: 1, allowCurrentProfile: true, dns: {nameserver: ['supplier.invalid']}, privateRules: ['MATCH,DIRECT']};
  // This is the required local-layer operation; runtime binding still needs real UI verification.
  delete input['x-routedeck-local']; input['x-routedeck-local'] = local();
  const out = run(input); assert.equal(out.dns, undefined); assert.equal(out.rules.length, 4);
});
test('unsupported protocol, provider input and ambiguous region are rejected', () => {
  for (const mutate of [x => x.proxies[0].type = 'wireguard', x => x['proxy-providers'] = {source: {type: 'http'}}, x => x.proxies[0].name = 'US HK mixed', x => x.proxies[0]['dialer-proxy'] = 'supplier']) {
    const x = fixture(); mutate(x); assert.throws(() => run(x), /unsupported|ambiguous/);
  }
});
test('all name collisions are rejected even when the source node would be excluded', () => {
  for (const name of ['US one', 'RouteDeck-US', 'RouteDeck-Terminal-Reject', 'DIRECT']) {
    const x = fixture(); x.proxies.push(node(name)); assert.throws(() => run(x), /name/);
  }
  const x = fixture(); x['x-routedeck-local'].privateProxies = [node('US one')]; assert.throws(() => run(x), /name/);
});
test('private rules and dependency closure cannot refer to vendor groups or introduce MATCH', () => {
  for (const rule of ['MATCH,DIRECT', 'DOMAIN,internal.invalid,vendor', 'RULE-SET,vendor,DIRECT']) {
    const x = fixture(); x['x-routedeck-local'].privateRules = [rule]; assert.throws(() => run(x), /private/);
  }
  const x = fixture(); x['x-routedeck-local'].privateGroups = [{name: 'a', type: 'select', proxies: ['b']}, {name: 'b', type: 'select', proxies: ['a']}];
  assert.throws(() => run(x), /cycle/);
});
test('public provider URLs, payloads and unique cache paths match stable rules', () => {
  const providers = Object.values(run(fixture())['rule-providers']);
  assert.equal(new Set(providers.map((p) => p.path)).size, 3);
  for (const p of providers) {
    assert(p.url.startsWith('https://raw.githubusercontent.com/NBStarry/RouteDeck-Rules/stable/v1/routing/rules/'));
    assert.equal(p.interval, 86400); assert.equal(p.proxy, 'RouteDeck-Proxy'); assert(p.payload.length > 0);
    const key = p.url.split('/').at(-1);
    const payload = fs.readFileSync(__dirname + '/../../rules/' + key, 'utf8').split('\n').filter((line) => line.startsWith('- ')).map((line) => line.slice(2).replace(/^['"]|['"]$/g, ''));
    assert.deepEqual(p.payload, payload);
  }
});
