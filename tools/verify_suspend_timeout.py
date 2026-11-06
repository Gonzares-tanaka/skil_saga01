"""Deterministic JS storage deadlines, including commit-vs-timeout ordering."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--playwright-path',type=Path,required=True)
    args=parser.parse_args()
    sys.path.insert(0,str(args.playwright_path.resolve()))
    from playwright.sync_api import sync_playwright
    result=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='msedge',headless=True)
        for mode in ('open_never_replies','active_abort','committed_before_deadline','open_replies_too_late'):
            page=browser.new_page()
            page.evaluate('''(mode)=>{
                window.mode=mode; window.uxClosed=false; window.puts=0; window.aborted=false;
                window.nativeTimer=window.setTimeout.bind(window);
                window.setTimeout=(fn,ms,...args)=>nativeTimer(fn,ms===10000?10:ms,...args);
                const factory={open(){
                    const request={};
                    if(mode==='open_never_replies') return request;
                    const db={close(){window.uxClosed=true;},transaction(){
                        const tx={objectStore(){return {put(){window.puts++;}};},abort(){
                            if(mode==='committed_before_deadline') throw new DOMException('already committed','InvalidStateError');
                            window.aborted=true; queueMicrotask(()=>tx.onabort());
                        }};
                        if(mode==='committed_before_deadline') nativeTimer(()=>tx.oncomplete(),35);
                        return tx;
                    }};
                    nativeTimer(()=>{request.result=db; request.onsuccess();},mode==='open_replies_too_late'?35:0);
                    return request;
                }};
                Object.defineProperty(window,'indexedDB',{value:factory,configurable:true});
            }''',mode)
            page.add_script_tag(content=(ROOT/'tools/web_suspend_store.js').read_text(encoding='utf8'))
            page.evaluate('window.job=window.sparkSuspendStore.start("write","checkpoint")')
            page.wait_for_function('window.job.done')
            page.wait_for_timeout(50)
            state=page.evaluate('({done:job.done,error:job.error,result:job.result,closed:uxClosed,puts,aborted})')
            if mode=='committed_before_deadline':
                assert not state['error'] and state['result'] is True and state['puts']==1,state
            else:
                assert state['error'] and state['result'] is None,state
            if mode=='open_replies_too_late': assert state['closed'] and state['puts']==0,state
            if mode=='active_abort': assert state['aborted'],state
            result.append(dict(mode=mode,**state)); page.close()
        browser.close()
    (ROOT/'verification/alpha_ux01_storage_timeout.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('PASS: four storage deadline/commit ordering cases')


if __name__=='__main__': main()
