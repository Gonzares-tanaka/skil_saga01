"""Run the exact reaccept UI transition in native Pyxel; retain full traceback."""
import argparse
import json
from pathlib import Path
import sys
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--window',action='store_true')
    parser.add_argument('--label',default='before')
    parser.add_argument('--cycles',type=int,default=2)
    args=parser.parse_args()
    from tests.quest_reaccept_flow import QuestFlow
    import pyxel
    flow=QuestFlow(window=args.window)
    result=dict(native_window=args.window,real_update_draw=True,
        actual_player_save_used=False,travel_position_fixture=True)
    output=ROOT/'verification';output.mkdir(exist_ok=True)
    try:
        flow.new_game()
        for i in range(args.cycles):
            flow.accept('hunt');flow.complete()
        result['success']=True
    except Exception:
        result.update(success=False,traceback=traceback.format_exc(),before_failed_update=flow.last_before)
        print(result['traceback'],flush=True)
        (output/f'quest_reaccept_{args.label}_trace.txt').write_text(result['traceback'],encoding='utf8')
    finally:
        result.update(state=flow.snapshot(),stages=flow.stages,inputs=flow.inputs)
        (output/f'quest_reaccept_{args.label}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        pyxel.screen.save(str(output/f'quest_reaccept_{args.label}.png'),4)
        flow.close()
    print('SUCCESS:',result['success'],'native window:',args.window,flush=True)
    raise SystemExit(0 if result['success'] else 1)


if __name__=='__main__':main()
