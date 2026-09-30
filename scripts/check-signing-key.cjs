#!/usr/bin/env node
'use strict';
// Validate entirely in memory. Never print a key or a parser exception.
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

function checkSigningKey(secret, publicPem, required = false) {
  if (!secret) return required ? 'missing' : 'unsigned';
  try {
    const privateKey = crypto.createPrivateKey({ key: secret, format: 'pem' });
    const publicKey = crypto.createPublicKey(publicPem);
    const actual = crypto.createPublicKey(privateKey).export({ type: 'spki', format: 'der' });
    const expected = publicKey.export({ type: 'spki', format: 'der' });
    if (!actual.equals(expected)) return 'mismatch';
    const probe = Buffer.from('CSQTT release signing preflight');
    return crypto.verify('sha256', probe, publicKey, crypto.sign('sha256', probe, privateKey))
      ? 'valid' : 'invalid';
  } catch { return 'invalid'; }
}

if (require.main === module) {
  const secret = process.env.CSQTT_SIGNING_KEY || '';
  delete process.env.CSQTT_SIGNING_KEY;
  const result = checkSigningKey(secret, fs.readFileSync(path.join(__dirname, '../release/csqtt-public.pem')),
    process.argv.includes('--required'));
  const messages = {
    unsigned: 'Signing secret absent; build artifacts will remain unsigned.',
    valid: 'Signing key is readable and matches the pinned project public key.',
    missing: 'Configure CSQTT_SIGNING_KEY or secret1 with the complete PEM private key.',
    invalid: 'Signing secret is not a readable PEM private key. Copy the complete file including BEGIN/END lines, without quotes or a file path.',
    mismatch: 'Signing key does not match the pinned project public key.',
  };
  if (result === 'valid' || result === 'unsigned') console.log(messages[result]);
  else { console.error(messages[result]); process.exitCode = 1; }
}
module.exports = { checkSigningKey };
