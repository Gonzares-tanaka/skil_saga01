"""Read/surgically replace Pyxel TOML audio blocks, without saving other data."""
from collections import defaultdict
import hashlib
import json
import re
import tomllib
import zipfile

ALLOWED_SOUNDS=set(range(7)) | set(range(14,21)) | {57,58}
ALLOWED_MUSICS={0,2}


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def read_resource(path):
    with zipfile.ZipFile(path) as archive:
        return tomllib.loads(archive.read('pyxel_resource.toml').decode('utf8'))


def blocks(raw):
    counters=defaultdict(int)
    # Also retain the preamble and any future non-audio tables byte for byte.
    result=[]
    for block in re.split(rb'(?=^\[\[[a-z_]+\]\]\r?$)',raw,flags=re.MULTILINE):
        match=re.match(rb'\[\[([a-z_]+)\]\]',block)
        kind=match[1].decode() if match else 'preamble'
        index=counters[kind]; counters[kind]+=1
        result.append((kind,index,block))
    return result


def raw_snapshot(path):
    with zipfile.ZipFile(path) as archive:
        raw=archive.read('pyxel_resource.toml')
        return dict(blocks={f'{kind}:{index}':hashlib.sha256(block).hexdigest() for kind,index,block in blocks(raw)},
            other_entries={name:hashlib.sha256(archive.read(name)).hexdigest() for name in archive.namelist()
                           if name!='pyxel_resource.toml'})


def assert_protected_resource(path,before,*,allowed_sounds=ALLOWED_SOUNDS,allowed_musics=ALLOWED_MUSICS):
    now=read_resource(path); old=before['scene']
    for kind,allowed in (('sounds',allowed_sounds),('musics',allowed_musics)):
        assert len(now[kind])==len(old[kind])
        for i,row in enumerate(now[kind]):
            if i not in allowed: assert row==old[kind][i],(kind,i)
    for key in set(now)|set(old):
        if key not in ('sounds','musics'): assert digest(now[key])==old[key],key
    snapshot=raw_snapshot(path)
    assert snapshot['other_entries']==before['raw']['other_entries']
    assert snapshot['blocks'].keys()==before['raw']['blocks'].keys()
    for key,value in before['raw']['blocks'].items():
        kind,index=key.split(':'); index=int(index)
        if kind=='sounds' and index in allowed_sounds or kind=='musics' and index in allowed_musics: continue
        assert snapshot['blocks'][key]==value,key


def replace_audio(path,sounds,musics):
    assert set(sounds)<=ALLOWED_SOUNDS and set(musics)<=ALLOWED_MUSICS
    with zipfile.ZipFile(path) as archive:
        entries=[(info,archive.read(info.filename)) for info in archive.infolist()]
    output=[]
    for info,raw in entries:
        if info.filename=='pyxel_resource.toml':
            edited=[]
            for kind,index,block in blocks(raw):
                data=sounds.get(index) if kind=='sounds' else musics.get(index) if kind=='musics' else None
                if data is not None:
                    block=(f'[[{kind}]]\n'+'\n'.join(f'{key} = {json.dumps(value)}' for key,value in data.items())+'\n\n').encode()
                edited.append(block)
            raw=b''.join(edited)
        output.append((info,raw))
    candidate=path.with_suffix('.audio-pass02.tmp')
    try:
        with zipfile.ZipFile(candidate,'w') as archive:
            for info,raw in output: archive.writestr(info,raw)
        # Parse and round-trip the complete candidate before replacing the resource.
        parsed=read_resource(candidate)
        assert all(parsed['sounds'][i]==row for i,row in sounds.items())
        assert all(parsed['musics'][i]==row for i,row in musics.items())
        candidate.replace(path)
    finally:
        if candidate.exists(): candidate.unlink()
