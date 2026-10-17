"""Bounded native API probe; kill only our own disposable child on timeout."""
import argparse
import faulthandler
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


def child(mode):
    import pyxel
    log=ROOT/'verification'/('gkd_audio_'+mode+'_stacks.txt')
    with log.open('w',encoding='utf8') as stream:
        faulthandler.enable(file=stream)
        faulthandler.dump_traceback_later(3,file=stream)
        pyxel.init(160,120,headless=True)
        pyxel.load(str(ROOT/'assets/battle_music.pyxres'),exclude_images=True,exclude_tilemaps=True)
        for i in range(1000):
            for c in (1,2,3): pyxel.stop(c)
            pyxel.play(0,59)
            print('REQUEST',mode,i,flush=True)
            if mode=='playm': pyxel.playm(0,loop=True)
            else:
                sequences=[list(sequence) for sequence in pyxel.musics[0].seqs]
                for channel,sequence in enumerate(sequences):
                    if sequence: pyxel.play(channel,sequence,loop=True)
            print('RETURN',mode,i,flush=True)
        faulthandler.cancel_dump_traceback_later()
        print('COMPLETE',flush=True)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--child',choices=('playm','channels'))
    args=parser.parse_args()
    if args.child: child(args.child); return
    results={}
    for mode in ('playm','channels'):
        start=time.monotonic()
        process=subprocess.Popen([sys.executable,'-B','-X','utf8',str(Path(__file__).resolve()),'--child',mode],
                                 cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf8')
        try:
            output,errors=process.communicate(timeout=10); timed_out=False
        except subprocess.TimeoutExpired:
            process.kill(); output,errors=process.communicate(); timed_out=True
        (ROOT/'verification'/('gkd_audio_'+mode+'.txt')).write_text(output+errors,encoding='utf8')
        results[mode]=dict(timed_out=timed_out,return_code=process.returncode,
                           completed=output.count('RETURN'),last_lines=output.splitlines()[-3:],
                           seconds=round(time.monotonic()-start,3))
        print(mode,results[mode],flush=True)
    (ROOT/'verification/gkd_audio_probe.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf8')


if __name__=='__main__': main()
