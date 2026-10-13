"""RFC 8785 section 3.2.3 vectors plus independent ECMAScript serialization."""
import json
import subprocess
import unittest

from engineering.evidence_admission.encoding import canonicalize, parse_canonical, EncodingError


class EncodingTests(unittest.TestCase):
    def test_rfc8785_utf16_property_order(self):
        # RFC 8785 section 3.2.3: input codepoints and independently specified order.
        keys = ['\u20ac', '\r', '\ufb33', '1', '\U0001f600', '\u0080', '\u00f6']
        value = {key: index for index, key in enumerate(keys)}
        self.assertEqual(list(json.loads(canonicalize(value))),
                         ['\r', '1', '\u0080', '\u00f6', '\u20ac', '\U0001f600', '\ufb33'])
        wrong = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
        with self.assertRaisesRegex(EncodingError, 'NONCANONICAL'):
            parse_canonical(wrong)

    def test_string_escaping_and_unicode_preservation(self):
        value = '\x00\b\t\n\f\r\x1f"\\/\u2028\u2029é'
        expected = '"\\u0000\\b\\t\\n\\f\\r\\u001f\\"\\\\/\u2028\u2029é"'.encode()
        self.assertEqual(canonicalize(value), expected)
        self.assertNotEqual(canonicalize('é'), canonicalize('e\u0301'))

    def test_independent_node_interoperability(self):
        # Stringify primitive values; sort UTF-16 keys before direct emission.
        # Reconstructing a JS object first would reorder integer-like keys.
        script = """import fs from 'node:fs';
        const emit = v => Array.isArray(v) ? '['+v.map(emit).join(',')+']'
          : v !== null && typeof v === 'object'
          ? '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+emit(v[k])).join(',')+'}'
          : JSON.stringify(v);
        process.stdout.write(emit(JSON.parse(fs.readFileSync(0,'utf8'))));"""
        values = [{'\ufb33': [None, True, False, -9007199254740991],
                   '\U0001f600': {'10': 10, '2': 2, '0': 0}, '\r': '\x00\n/é'},
                  {'a': '\u2028\u2029', 'é': 'e\u0301', 'z': 9007199254740991}]
        for value in values:
            with self.subTest(value=value):
                result = subprocess.run(['node', '--input-type=module', '-e', script],
                                        input=json.dumps(value).encode(), capture_output=True, check=True)
                self.assertEqual(canonicalize(value), result.stdout)
                self.assertEqual(parse_canonical(result.stdout), value)

    def test_reject_duplicate_keys_at_any_depth(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":{"b":1,"b":1}}', b'{"a":1,"\\u0061":1}'):
            with self.subTest(raw=raw), self.assertRaisesRegex(EncodingError, 'DUPLICATE_KEY'):
                parse_canonical(raw)

    def test_reject_noncanonical_and_unsupported_numbers(self):
        values = [b' 0', b'0\n', b'-0', b'1.0', b'1e0', b'NaN', b'Infinity',
                  b'9007199254740992', b'-9007199254740992', b'9'*5000, b'"\\u0061"',
                  b'"\\/"', b'{"z":0,"a":1}', b'\xef\xbb\xbf{}']
        for raw in values:
            with self.subTest(raw=raw), self.assertRaises(EncodingError):
                parse_canonical(raw)

    def test_reject_unicode_and_unsupported_python_values(self):
        for raw in (b'"\\ud800"', b'"\\udfff"', b'"\xff"'):
            with self.subTest(raw=raw), self.assertRaises(EncodingError):
                parse_canonical(raw)
        for value in (1.0, float('nan'), (1,), {1: 'not-string'}, '\ud800'):
            with self.subTest(value=repr(value)), self.assertRaises(EncodingError):
                canonicalize(value)

    def test_limits_and_exact_types(self):
        with self.assertRaises(EncodingError):
            parse_canonical('{}')
        with self.assertRaises(EncodingError):
            parse_canonical(b' ' * (4 * 1024 * 1024 + 1))
        with self.assertRaises(EncodingError):
            canonicalize(json.loads('[' * 65 + '0' + ']' * 65))
