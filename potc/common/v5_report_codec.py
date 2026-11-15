"""Exact, single-file validation JSON packaging; no acceptance predicates.

Plain JSON remains supported. An explicit zlib/base64 envelope carries the
complete original UTF-8 JSON bytes, size and SHA256, never a substitute PASS.
The frozen v4 checker receives the original decoded text at one scoped path.
"""
from __future__ import annotations

import argparse
import base64
import binascii
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import tempfile
import types
import zlib

ENCODING = 'potc-validation-zlib-base64-v1'
FIELDS = {'encoding', 'uncompressed_sha256', 'uncompressed_size', 'payload'}
MAX_UNCOMPRESSED = 512 * 1024 * 1024


class CodecError(ValueError):
    pass


def require(test, message):
    if not test:
        raise CodecError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(raw):
    try:
        return json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise CodecError('Invalid validation JSON') from exc


def _envelope(value):
    return isinstance(value, dict) and (
        value.get('encoding') == ENCODING or set(value) == FIELDS
        or isinstance(value.get('encoding'), str) and value['encoding'].startswith('potc-validation-'))


def _inflate(value):
    require(set(value) == FIELDS, 'Incomplete or extra validation-envelope fields')
    require(value.get('encoding') == ENCODING, 'Unknown validation-envelope encoding')
    size, expected, payload = value['uncompressed_size'], value['uncompressed_sha256'], value['payload']
    require(type(size) is int and 0 < size <= MAX_UNCOMPRESSED, 'Invalid/oversized decoded validation size')
    require(isinstance(expected, str) and re.fullmatch('[0-9a-f]{64}', expected), 'Invalid decoded validation SHA256')
    require(isinstance(payload, str), 'Validation payload must be base64 text')
    try:
        packed = base64.b64decode(payload, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise CodecError('Invalid validation base64 payload') from exc
    try:
        stream = zlib.decompressobj()
        raw = stream.decompress(packed, size + 1)
    except zlib.error as exc:
        raise CodecError('Invalid validation zlib stream') from exc
    require(len(raw) == size, 'Decoded validation size differs')
    require(stream.eof and not stream.unused_data and not stream.unconsumed_tail,
            'Truncated, trailing or concatenated validation zlib data')
    require(sha(raw) == expected, 'Decoded validation SHA256 differs')
    return raw


def _unpack(raw):
    require(isinstance(raw, bytes) and len(raw) <= MAX_UNCOMPRESSED * 2,
            'Validation input must be bounded bytes')
    value = _json(raw)
    if _envelope(value):
        decoded = _inflate(value)
        result = _json(decoded)
        require(not _envelope(result), 'Nested validation envelopes are unsupported')
        return decoded, result
    require(len(raw) <= MAX_UNCOMPRESSED, 'Plain validation exceeds the decoded-size limit')
    return raw, value


def decode_bytes(raw):
    """Return exactly the original JSON bytes, or unchanged plain JSON bytes."""
    return _unpack(raw)[0]


def encode_bytes(raw):
    """Idempotently encode complete JSON, preserving every original byte."""
    original, parsed = _unpack(raw)
    del parsed
    value = {'encoding': ENCODING, 'uncompressed_sha256': sha(original),
             'uncompressed_size': len(original),
             'payload': base64.b64encode(zlib.compress(original, 9)).decode('ascii')}
    encoded = (json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')
    require(decode_bytes(encoded) == original, 'Validation encoder byte-roundtrip failed')
    return encoded


def read(path):
    """Read the full ordinary report object; encoded envelope flags never gate."""
    return _unpack(Path(path).read_bytes())[1]


def read_text(path, encoding='utf-8', errors='strict'):
    raw = decode_bytes(Path(path).read_bytes())
    # Match Path.read_text's universal-newline behavior, without changing the
    # bytes retained by encode/decode or the parsed JSON values.
    text = raw.decode(encoding or 'utf-8', errors or 'strict')
    return text.replace('\r\n', '\n').replace('\r', '\n')


@contextmanager
def validation_text_boundary(module, asset):
    """Temporarily decode only this exact validation path for frozen V.check.

    No global pathlib/json methods, files or frozen predicate code are changed.
    Separate check subprocesses retain independent module aliases.
    """
    original = module.Path
    target = (Path(asset).resolve() / 'validation.json').resolve()
    platform_path = type(Path())

    class ValidationPath(platform_path):
        def read_text(self, encoding=None, errors=None):
            if self.resolve() == target:
                return read_text(self, encoding or 'utf-8', errors or 'strict')
            return super().read_text(encoding=encoding, errors=errors)

    module.Path = ValidationPath
    try:
        yield
    finally:
        module.Path = original


def _same_types(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, float):
        return struct.pack('!d', a) == struct.pack('!d', b)
    if isinstance(a, dict):
        return list(a) == list(b) and all(_same_types(a[key], b[key]) for key in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(_same_types(x, y) for x, y in zip(a, b))
    return a == b


def self_test():
    original = b'{"i":1,"f":1.0,"negzero":-0.0,"big":18446744073709551617,"yes":true,"none":null,"items":["\\u0142",{},[]]}\n'
    wire = encode_bytes(original); envelope = json.loads(wire)
    require(decode_bytes(original) == original and decode_bytes(wire) == original, 'Plain/encoded byte identity failed')
    require(encode_bytes(wire) == wire and _same_types(json.loads(original), _unpack(wire)[1]), 'Idempotence or numeric/type identity failed')
    cases = {
        'unknown encoding': {**envelope, 'encoding': 'unsupported'},
        'invalid base64': {**envelope, 'payload': envelope['payload'] + '!'},
        'truncated zlib': {**envelope, 'payload': base64.b64encode(base64.b64decode(envelope['payload'])[:-1]).decode()},
        'trailing zlib': {**envelope, 'payload': base64.b64encode(base64.b64decode(envelope['payload']) + b'extra').decode()},
        'concatenated zlib': {**envelope, 'payload': base64.b64encode(base64.b64decode(envelope['payload']) + zlib.compress(b'{}')).decode()},
        'wrong hash': {**envelope, 'uncompressed_sha256': '0' * 64},
        'wrong size': {**envelope, 'uncompressed_size': len(original) + 1},
        'short size': {**envelope, 'uncompressed_size': len(original) - 1},
        'boolean size': {**envelope, 'uncompressed_size': True},
        'oversized decode': {**envelope, 'uncompressed_size': MAX_UNCOMPRESSED + 1},
        'extra field': {**envelope, 'passed': True},
        'missing field': {key: value for key, value in envelope.items() if key != 'payload'},
    }
    for label, value in cases.items():
        try:
            decode_bytes(json.dumps(value).encode())
        except CodecError:
            pass
        else:
            raise CodecError('Corrupt envelope accepted: ' + label)
    with tempfile.TemporaryDirectory() as folder:
        asset = Path(folder); (asset / 'validation.json').write_bytes(wire)
        other = asset / 'spec.json'; other.write_text('not JSON; must be delegated verbatim')
        module = types.SimpleNamespace(Path=Path)
        with validation_text_boundary(module, asset):
            require(module.Path is not Path and module.Path(asset / 'validation.json').read_text() == original.decode(), 'Exact validation boundary did not decode')
            require(module.Path(other).read_text() == other.read_text(), 'Boundary changed another path')
            require(Path(asset / 'validation.json').read_bytes() == wire, 'Boundary materialized/mutated a file')
        require(module.Path is Path, 'Path alias was not restored')
        try:
            with validation_text_boundary(module, asset):
                raise RuntimeError('controlled failure')
        except RuntimeError:
            pass
        require(module.Path is Path, 'Path alias was not restored after failure')
    return {'passed': True, 'controls': ['plain report unchanged', 'exact bytes and numeric types', 'idempotent encoding',
            *cases, 'one exact-path text boundary', 'other paths/global Path untouched', 'alias restored normally and after failure'],
            'scope': 'Lossless report serialization controls only; no ship predicates or release acceptance claim.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--encode', type=Path); group.add_argument('--decode', type=Path)
    group.add_argument('--self-test', action='store_true')
    parser.add_argument('--output', type=Path, help='Encode defaults to in-place; decode defaults to stdout')
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), indent=2)); return
    source = args.encode or args.decode; raw = source.read_bytes()
    result = encode_bytes(raw) if args.encode else decode_bytes(raw)
    destination = args.output or (source if args.encode else None)
    if destination is None:
        sys.stdout.buffer.write(result); return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=destination.name + '.', suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name); handle.write(result)
        temporary.replace(destination); temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print(json.dumps({'operation': 'encode' if args.encode else 'decode', 'path': str(destination),
                      'input_bytes': len(raw), 'output_bytes': len(result), 'decoded_sha256': sha(decode_bytes(result))}, indent=2))


if __name__ == '__main__':
    main()
