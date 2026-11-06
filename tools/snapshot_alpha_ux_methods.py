"""Recover method-level pre-change proof from the clean, matching Git HEAD."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
FILES=('rpg/models.py','rpg/battle.py','rpg/app.py','rpg/dungeon_app.py')


def method_hashes(source):
    result={}
    for node in ast.parse(source).body:
        if isinstance(node,ast.FunctionDef):
            result[node.name]=hashlib.sha256(ast.get_source_segment(source,node).encode()).hexdigest()
        elif isinstance(node,ast.ClassDef):
            for method in node.body:
                if isinstance(method,ast.FunctionDef):
                    result[node.name+'.'+method.name]=hashlib.sha256(ast.get_source_segment(source,method).encode()).hexdigest()
    return result


def main():
    path=ROOT/'tests/fixtures/alpha_ux01_before.json'
    before=json.loads(path.read_text(encoding='utf-8-sig'))
    if 'methods' in before: raise FileExistsError('Method proof already exists')
    methods={}
    for name in FILES:
        raw=subprocess.check_output(['git','show','HEAD:'+name],cwd=ROOT)
        assert hashlib.sha256(raw).hexdigest()==before['hashes'][name],name
        methods[name]=method_hashes(raw.decode('utf8'))
    before['methods']=methods
    path.write_text(json.dumps(before,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('Verified HEAD matches original file hashes; recorded method proof')


if __name__=='__main__': main()
