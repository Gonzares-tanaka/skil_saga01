"""Separate opt-in diagnostic ZIP, preserving the normal ZIP and save folder."""
import ast
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
NORMAL=ROOT/'verification/packages/skill_seekers_gkd.zip'
OUTPUT=NORMAL.with_name('skill_seekers_gkd_diagnostic.zip')
GUIDE='''GKD Pixel 2 戦闘開始診断版

ZIPを展開し、Skill_Seekersフォルダを既存フォルダへ「上書き/結合」します。
既存のsaveフォルダは削除しないでください。ZIPにはセーブを含みません。
Skill_Seekers_Diagnostic.shを既存Skill_Seekers.shと同じ階層へコピーします。
診断時はSkill_Seekers_Diagnostic.shを起動してください。
通常ランチャーの名前/内容はこのZIPでは上書きしません。
診断ランチャーも既存のsave/save.jsonを使い、既存SAVE/LOADの仕様のままです。

Skill_Seekers/diagnostic_config.jsonをメモ帳で編集できます。
デフォルト: battle_start_audio=true, skip_transition=false, watchdog_seconds=20
まずデフォルトで試してください。
比較B: battle_start_audio=false（戦闘突入SE/BGM要求だけ無効、戦闘ロジックは同じ）
比較C: skip_transition=true（既存の演出なし開始経路を診断時だけ使用）
2つ同時に変えず、一度に1項目を変更してください。設定は次回起動から有効です。

フリーズ後はPC/ファイルマネージャーで以下を回収してください。
Skill_Seekers/diagnostics/battle_start.jsonl
Skill_Seekers/diagnostics/battle_start.jsonl.1（あれば）
Skill_Seekers/diagnostics/python_stacks.log
Skill_Seekers/diagnostics/python_stacks.log.1（あれば）
ランチャーと同じフォルダ/skill_seekers_diagnostic_launch.log
save/save.jsonの提出は不要です。

ログはCheckpointごとにflush、戦闘開始音声要求直前/COMMAND_READY/例外ではfsync。
JSONLは最大256KiB×2。スタックは20秒更新が途絶えたとき1回出力します。
faulthandler未対応時はWATCHDOG_UNAVAILABLEを記録し、Checkpointは継続します。
input lock中にボタンが押され続けている場合はINPUT_HELDでキー番号を記録します。
ログを編集/消去する場合はゲームを終了してから行ってください。

この診断版にもネイティブplaym停止の最小回避を含みます。
Skill、Enemy、マップ、SAVE形式、遷移タイマーは通常修正版と同じです。
診断が不要になったら通常Skill_Seekers.shから起動できます。
'''


def main():
    digest=hashlib.sha256(NORMAL.read_bytes()).hexdigest()
    launcher=(ROOT/'tools/run_gkd.sh').read_text(encoding='utf8').replace('skill_seekers_launch.log','skill_seekers_diagnostic_launch.log').replace('-u main.py','-u diagnostic_main.py')
    with zipfile.ZipFile(NORMAL) as normal,zipfile.ZipFile(OUTPUT,'w',compression=zipfile.ZIP_DEFLATED) as target:
        for info in normal.infolist():
            if info.filename!='Skill_Seekers.sh': target.writestr(info,normal.read(info.filename))
        launch_info=zipfile.ZipInfo('Skill_Seekers_Diagnostic.sh'); launch_info.create_system=3
        launch_info.external_attr=0o100755<<16; launch_info.compress_type=zipfile.ZIP_DEFLATED
        target.writestr(launch_info,launcher.replace('\r\n','\n'))
        target.writestr('Skill_Seekers/diagnostic_main.py',(ROOT/'tools/gkd_diagnostic.py').read_bytes())
        target.writestr('Skill_Seekers/diagnostic_config.json',json.dumps(dict(battle_start_audio=True,skip_transition=False,watchdog_seconds=20),indent=2)+'\n')
        target.writestr('DIAGNOSTIC_README.txt',GUIDE)
    assert hashlib.sha256(NORMAL.read_bytes()).hexdigest()==digest
    with zipfile.ZipFile(OUTPUT) as z:
        names=z.namelist(); assert not any('/save/' in n for n in names)
        for name in names:
            if name.endswith('.py'): ast.parse(z.read(name).decode('utf8'),feature_version=(3,11))
        with zipfile.ZipFile(NORMAL) as normal:
            for name in normal.namelist():
                if name!='Skill_Seekers.sh': assert z.read(name)==normal.read(name),name
    report=dict(entries=len(names),save_excluded=True,normal_zip_unchanged_by_diagnostic_build=True,
                python_311_syntax=True,normal_sources_exact=True,path=OUTPUT.relative_to(ROOT).as_posix())
    (ROOT/'verification/gkd_diagnostic_package.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print('Built separate diagnostic:',OUTPUT.relative_to(ROOT).as_posix(),'entries:',len(names))


if __name__=='__main__': main()
