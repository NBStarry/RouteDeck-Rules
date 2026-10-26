// Party profile overrides: trusted PC local preparation first, this remote policy second.
// The marker is an interface, not authentication. Verify the actual binding order.
function main(config) {
  const fail = (message) => { throw new Error('RouteDeck Party: ' + message); };
  const object = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
  const copy = (value) => JSON.parse(JSON.stringify(value));
  if (!object(config)) fail('expected configuration object');
  const local = config['x-routedeck-local'];
  if (!object(local) || local.version !== 1 || local.allowCurrentProfile !== true) fail('local preparation missing or invalid');
  for (const key of ['excludeNodeNames', 'privateRules', 'privateProxies', 'privateGroups']) {
    if (!Array.isArray(local[key])) fail('missing local array: ' + key);
  }
  if (local.excludeNodeNames.some((name) => typeof name !== 'string')) fail('invalid exclusion names');
  if (config['proxy-providers'] !== undefined && (!object(config['proxy-providers']) || Object.keys(config['proxy-providers']).length)) fail('provider input is unsupported; use expanded subscription nodes');
  if (!Array.isArray(config.proxies)) fail('expanded subscription nodes required');
  const regions = ['US', 'TW', 'HK', 'SG'];
  const managed = regions.concat(['OpenAI', 'Proxy']).map((r) => 'RouteDeck-' + r);
  const terminal = 'RouteDeck-Terminal-Reject';
  const names = new Set(['DIRECT', 'REJECT', 'REJECT-DROP', 'PASS', 'COMPATIBLE', terminal, ...managed]);
  const register = (item) => {
    if (!object(item) || typeof item.name !== 'string' || !item.name.trim() || /[\r\n,]/.test(item.name) || names.has(item.name)) fail('invalid or duplicate outbound name');
    names.add(item.name);
  };
  local.privateProxies.forEach(register);
  local.privateGroups.forEach(register);
  const privateNames = new Set(local.privateProxies.concat(local.privateGroups).map((item) => item.name));
  const nodes = [];
  const members = regions.map(() => []);
  const patterns = [/🇺🇸|美国|美國|(?:^|[^A-Za-z])(?:US|USA|United States)(?=$|[^A-Za-z])/i, /🇹🇼|台湾|台灣|(?:^|[^A-Za-z])(?:TW|Taiwan)(?=$|[^A-Za-z])/i, /🇭🇰|香港|(?:^|[^A-Za-z])(?:HK|Hong Kong)(?=$|[^A-Za-z])/i, /🇸🇬|新加坡|狮城|獅城|(?:^|[^A-Za-z])(?:SG|Singapore)(?=$|[^A-Za-z])/i];
  const protocols = ['ss', 'ssr', 'vmess', 'vless', 'trojan', 'hysteria', 'hysteria2', 'tuic', 'snell', 'mieru', 'anytls'];
  const excluded = new Set(local.excludeNodeNames);
  for (const node of config.proxies) {
    register(node);
    if (excluded.has(node.name) || /manual[-_ ]?only|ikuuu/i.test(node.name)) continue;
    if (!protocols.includes(node.type)) fail('unsupported subscription protocol');
    if (node['dialer-proxy'] !== undefined) fail('subscription dialer dependency is unsupported');
    const matches = patterns.flatMap((pattern, i) => pattern.test(node.name) ? [i] : []);
    if (matches.length > 1) fail('ambiguous node region');
    if (!matches.length) continue; // Only the four configured regions are candidates.
    nodes.push(copy(node));
    members[matches[0]].push(node.name);
  }
  const builtins = new Set(['DIRECT', 'REJECT', 'REJECT-DROP']);
  const privateReference = (name) => {
    if (typeof name !== 'string' || (!privateNames.has(name) && !builtins.has(name))) fail('unresolved private outbound reference');
  };
  for (const node of local.privateProxies) {
    if (typeof node.type !== 'string' || !node.type) fail('invalid private proxy');
    if (node['dialer-proxy'] !== undefined) privateReference(node['dialer-proxy']);
  }
  for (const group of local.privateGroups) {
    if (!['select', 'fallback', 'url-test', 'load-balance'].includes(group.type) || !Array.isArray(group.proxies) || !group.proxies.length) fail('unsupported private group');
    if (group.use !== undefined || group['include-all'] || group['include-all-proxies'] || group['include-all-providers']) fail('dynamic private group is unsupported');
    group.proxies.forEach(privateReference);
  }
  const dependencies = new Map(local.privateProxies.concat(local.privateGroups).map((item) => [item.name, item.proxies || (item['dialer-proxy'] ? [item['dialer-proxy']] : [])]));
  const done = new Set();
  const visit = (name, active = new Set()) => {
    if (done.has(name) || builtins.has(name)) return;
    if (active.has(name)) fail('private outbound dependency cycle');
    active.add(name);
    for (const child of dependencies.get(name) || []) visit(child, active);
    active.delete(name);
    done.add(name);
  };
  privateNames.forEach((name) => visit(name));
  const rules = local.privateRules.map((rule) => {
    if (typeof rule !== 'string') fail('invalid private rule');
    const parts = rule.split(',');
    if (!['DOMAIN', 'DOMAIN-SUFFIX', 'DOMAIN-KEYWORD', 'IP-CIDR', 'IP-CIDR6', 'IP-ASN', 'SRC-IP-CIDR', 'DST-PORT', 'SRC-PORT', 'PROCESS-NAME', 'PROCESS-PATH'].includes(parts[0]) || !parts[1] || (parts.length !== 3 && !(parts.length === 4 && parts[3] === 'no-resolve'))) fail('unsupported private rule');
    privateReference(parts[2]);
    return rule;
  });
  const groups = regions.map((region, i) => ({name: 'RouteDeck-' + region, type: 'fallback', proxies: members[i].concat(terminal), url: 'https://www.gstatic.com/generate_204', interval: 300, lazy: true}));
  for (const name of ['OpenAI', 'Proxy']) groups.push({name: 'RouteDeck-' + name, type: 'select', proxies: managed.slice(0, 4)});
  const payloads = {
    openai: ['chatgpt.com', 'openai.com', 'oaistatic.com', 'oaiusercontent.com'].map((d) => 'DOMAIN-SUFFIX,' + d),
    us: ['anthropic.com', 'claude.ai', 'claude.com', 'claudeusercontent.com', 'google.com', 'googleapis.com', 'gstatic.com', 'googleusercontent.com'].map((d) => 'DOMAIN-SUFFIX,' + d),
    direct: ['DOMAIN,api.deepseek.com']
  };
  const providers = {};
  for (const key of Object.keys(payloads)) providers['RouteDeck-' + key] = {type: 'http', behavior: 'classical', format: 'yaml', url: 'https://raw.githubusercontent.com/NBStarry/RouteDeck-Rules/stable/v1/routing/rules/' + key + '.yaml', path: './rules/routedeck/party-v1/' + key + '.yaml', interval: 86400, proxy: 'RouteDeck-Proxy', payload: payloads[key]};
  const out = {
    proxies: copy(local.privateProxies).concat(nodes, {name: terminal, type: 'reject'}),
    'proxy-groups': copy(local.privateGroups).concat(groups),
    'rule-providers': providers,
    rules: rules.concat('RULE-SET,RouteDeck-openai,RouteDeck-OpenAI', 'RULE-SET,RouteDeck-us,RouteDeck-US', 'RULE-SET,RouteDeck-direct,DIRECT', 'MATCH,RouteDeck-Proxy')
  };
  for (const key of ['dns', 'hosts']) {
    if (local[key] !== undefined) {
      if (!object(local[key])) fail('invalid local ' + key);
      out[key] = copy(local[key]);
    }
  }
  return out;
}
