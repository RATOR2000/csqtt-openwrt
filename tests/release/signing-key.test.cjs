'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { checkSigningKey } = require('../../scripts/check-signing-key.cjs');

function pair() {
  return crypto.generateKeyPairSync('ec', { namedCurve: 'prime256v1',
    privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
    publicKeyEncoding: { type: 'spki', format: 'pem' } });
}

test('signing preflight accepts matching PEM and rejects unreadable or unrelated secrets', () => {
  const key = pair();
  assert.equal(checkSigningKey('', key.publicKey), 'unsigned');
  assert.equal(checkSigningKey('', key.publicKey, true), 'missing');
  assert.equal(checkSigningKey(key.privateKey, key.publicKey, true), 'valid');
  assert.equal(checkSigningKey(key.privateKey.replaceAll('\n', '\r\n'), key.publicKey), 'valid');
  assert.equal(checkSigningKey(pair().privateKey, key.publicKey), 'mismatch');
  for (const value of ['private-key.pem', 'secret1', JSON.stringify(key.privateKey), key.publicKey])
    assert.equal(checkSigningKey(value, key.publicKey), 'invalid');
});

test('CLI fails before building and never echoes the secret or parser diagnostics', () => {
  const secret = crypto.randomBytes(32).toString('hex');
  const result = spawnSync(process.execPath,
    [path.resolve(__dirname, '../../scripts/check-signing-key.cjs'), '--required'],
    { encoding: 'utf8', env: { ...process.env, CSQTT_SIGNING_KEY: secret } });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /not a readable PEM private key/);
  assert.equal((result.stdout + result.stderr).includes(secret), false);
  assert.doesNotMatch(result.stderr, /error:|DECODER|stack|at /);
});
