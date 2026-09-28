// Independent Node.js implementation of the byte profile, not a compiler runtime.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(process.argv[2] ?? 'test-corpus/canonical');
const maxBytes = 1048576;
function encode(value, depth = 0) {
  if (depth > 48) throw Error('depth');
  if (value === null || typeof value === 'boolean') return JSON.stringify(value);
  if (typeof value === 'number' && Number.isSafeInteger(value)) return JSON.stringify(value);
  if (typeof value === 'string') {
    if (!value.isWellFormed()) throw Error('surrogate');
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return '[' + value.map(v => encode(v, depth + 1)).join(',') + ']';
  if (typeof value === 'object' && value !== null) {
    return '{' + Object.keys(value).sort().map(k => encode(k, depth + 1) + ':' + encode(value[k], depth + 1)).join(',') + '}';
  }
  throw Error('unsupported value');
}
function bytes(value) {
  const result = Buffer.from(encode(value), 'utf8');
  if (result.length > maxBytes) throw Error('size');
  return result;
}
function digest(value, domain) {
  return 'sha256:' + createHash('sha256').update('ACP\0acp-jcs-safe-v1\0' + domain + '\0').update(bytes(value)).digest('hex');
}
function parse(raw) {
  if (raw.length > maxBytes || raw.subarray(0, 3).equals(Buffer.from([239, 187, 191]))) throw Error('size/bom');
  const text = new TextDecoder('utf-8', { fatal: true }).decode(raw);
  let i = 0;
  const skip = () => { while (/[ \t\r\n]/.test(text[i] ?? 'x')) i++; };
  function string() {
    const match = /^"(?:[^"\\\u0000-\u001f]|\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4}))*"/.exec(text.slice(i));
    if (!match) throw Error('string');
    i += match[0].length;
    return JSON.parse(match[0]);
  }
  function value(depth) {
    if (depth > 48) throw Error('depth');
    skip();
    if (text[i] === '"') return string();
    if (text[i] === '{' || text[i] === '[') {
      const object = text[i++] === '{', end = object ? '}' : ']';
      const result = object ? Object.create(null) : [];
      skip();
      if (text[i] === end) { i++; return result; }
      for (;;) {
        skip();
        if (object) {
          const key = string();
          if (Object.hasOwn(result, key)) throw Error('duplicate');
          skip();
          if (text[i++] !== ':') throw Error('colon');
          result[key] = value(depth + 1);
        } else result.push(value(depth + 1));
        skip();
        if (text[i] === end) { i++; return result; }
        if (text[i++] !== ',') throw Error('comma');
      }
    }
    const match = /^(?:null|true|false|-?(?:0|[1-9][0-9]*))/.exec(text.slice(i));
    if (!match) throw Error('token');
    i += match[0].length;
    return JSON.parse(match[0]);
  }
  const result = value(0);
  skip();
  if (i !== text.length) throw Error('trailing');
  bytes(result);
  return result;
}

const vectors = parse(readFileSync(resolve(root, 'byte-vectors.json')));
assert.equal(vectors.profile, 'acp-jcs-safe-v1');
for (const vector of vectors.positive) {
  const value = parse(Buffer.from(vector.input, 'utf8'));
  assert.equal(bytes(value).toString('utf8'), vector.canonical, vector.name);
  assert.equal(digest(value, 'vector'), vector.digest, vector.name);
}
for (const vector of vectors.negative) {
  assert.throws(() => parse(Buffer.from(vector.input, 'utf8')), undefined, vector.name);
}
assert.throws(() => parse(Buffer.from([0xff])));
assert.throws(() => parse(Buffer.alloc(maxBytes + 1, 32)));
const manifest = parse(readFileSync(resolve(root, 'manifest.json')));
for (const example of manifest.examples) {
  const snapshot = parse(readFileSync(resolve(root, example.file)));
  assert.equal(digest(snapshot.content, 'canonical'), example.contentDigest);
  assert.equal(snapshot.contentDigest, example.contentDigest);
}
console.log(`Canonical byte profile PASS: ${vectors.positive.length} positive, ${vectors.negative.length} negative, ${manifest.examples.length} snapshot hashes; ${process.version}`);
