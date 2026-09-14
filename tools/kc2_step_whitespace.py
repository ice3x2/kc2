"""CON-ARCH-006 AC-9 pure lexical-only canonical STEP normalization.

Raw reviewed source/native artifacts are never written by this module. Only
outside-token trailing ASCII space/tab may disappear; line endings, comments,
strings, binary literals and every non-whitespace byte remain unchanged.
"""
import hashlib
import re

ALGORITHM='step-outside-token-trailing-ascii-v1'
TRAILING=re.compile(rb'[ \t]+(?=\r\n|\r|\n|\Z)')
SPACE=re.compile(rb'[ \t\r\n]+')
# Final alternatives deliberately expose unmatched delimiters to fail closed.
TOKENS=re.compile(rb'/\*.*?\*/|\'(?:[^\']|\'\')*\'|"[^"]*"|/\*|\*/|\'|"',re.S)


def _lex(raw):
    protected=[];signature=[];code=[];cursor=0
    for match in TOKENS.finditer(raw):
        token=match.group()
        if token in (b'/*',b'*/',b"'",b'"'):
            raise ValueError('Unterminated or unmatched STEP lexical construct')
        outside=SPACE.sub(b'',raw[cursor:match.start()])
        signature.extend((outside,token));code.append(outside)
        # Literal text may not masquerade as a section-framing keyword.
        if not token.startswith(b'/*'):code.append(b'?')
        protected.append((match.start(),match.end()));cursor=match.end()
    tail=SPACE.sub(b'',raw[cursor:]);signature.append(tail);code.append(tail)
    framing=b''.join(code)
    if (not framing.startswith(b'ISO-10303-21;HEADER;') or b'ENDSEC;DATA;' not in framing
        or not framing.endswith(b'ENDSEC;END-ISO-10303-21;')):
        raise ValueError('Unsupported or malformed STEP exchange framing')
    return protected,b''.join(signature)


def normalize(raw):
    if not isinstance(raw,bytes):raise TypeError('Raw STEP bytes required')
    protected,signature=_lex(raw)
    spans=[];index=0
    for match in TRAILING.finditer(raw):
        a,b=match.span()
        while index<len(protected) and protected[index][1]<=a:index+=1
        if index<len(protected) and protected[index][0]<b:
            raise ValueError('Trailing whitespace inside a protected STEP token/comment')
        spans.append((a,b))
    chunks=[];cursor=0
    for a,b in spans:
        chunks.append(raw[cursor:a]);cursor=b
    chunks.append(raw[cursor:]);normalized=b''.join(chunks)
    # Independent lexical pass plus exact deleted-byte reconstruction. No CAD,
    # entity, numeric, quoted-string or comment change can be approved here.
    _,after_signature=_lex(normalized)
    if signature!=after_signature or TRAILING.search(normalized):
        raise ValueError('STEP lexical equivalence or whitespace postcondition failed')
    rebuilt=[];cursor=0;output_cursor=0
    for a,b in spans:
        width=a-cursor;rebuilt.append(normalized[output_cursor:output_cursor+width]);output_cursor+=width
        rebuilt.append(raw[a:b]);cursor=b
    rebuilt.append(normalized[output_cursor:])
    if b''.join(rebuilt)!=raw:raise ValueError('Deletion reconstruction failed')
    return normalized,dict(algorithm=ALGORITHM,raw_sha256=hashlib.sha256(raw).hexdigest(),
        normalized_sha256=hashlib.sha256(normalized).hexdigest(),
        removed_bytes=sum(b-a for a,b in spans),removed_lines=len(spans),
        lexical_sha256=hashlib.sha256(signature).hexdigest(),
        step_has_trailing_whitespace=False,lexical_equivalence=True)
