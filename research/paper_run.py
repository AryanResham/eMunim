"""Finite measured paper suite supervisor. Real-data gaps remain explicit."""
import argparse
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from services.storage import write_json
from publish import publish


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run-id',required=True)
    args=parser.parse_args()
    if not args.run_id.replace('-','').replace('_','').isalnum():raise ValueError('Invalid run ID')
    folder=ROOT/'backend/data/paper_runs'/args.run_id;folder.mkdir(parents=True,exist_ok=True)
    lock=(folder.parent/'benchmark.lock').open('a+b')
    if sys.platform=='win32':
        import msvcrt
        lock.seek(0);lock.write(b'1');lock.flush();lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    else:
        import fcntl
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    write_json(folder.parent/'latest.json',{'run_id':args.run_id})
    state={'status':'running','run_id':args.run_id,'pid':os.getpid(),'started_at':datetime.now(timezone.utc).isoformat()}
    def command(name,arguments):
        state.update(phase=name,updated_at=datetime.now(timezone.utc).isoformat());write_json(folder/'status.json',state);publish(folder,'running')
        with (folder/(name+'.log')).open('a',encoding='utf-8') as log:
            completed=subprocess.run([sys.executable,'-u',*arguments],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        if completed.returncode:raise RuntimeError(f'{name} failed; inspect its saved log (exit {completed.returncode})')
        print(name+': complete',flush=True)
    try:
        command('dataset_audit',['research/dataset_audit.py',str(folder/'dataset_audit.json')])
        command('held_out_checkpoints',['research/checkpoint_eval.py','--out',str(folder/'checkpoints')])
        command('production_ocr_pilot',['research/paper_experiment.py','--out',str(folder/'pipelines'),'--live','--max-calls','220','--development-per-type','5','--test-per-type','6'])
        pipeline=json.loads((folder/'pipelines/pipeline_report.json').read_text(encoding='utf-8'))
        failures=sum(p['failures'] for p in pipeline['pipelines'].values())
        status='completed_with_failures' if failures else 'complete'
        publish(folder,status)
        state.update(status=status,phase='finished',pipeline_operational_failures=failures,finished_at=datetime.now(timezone.utc).isoformat())
        write_json(folder/'status.json',state)
        return 0
    except Exception as exc:
        state.update(status='failed',error=str(exc),finished_at=datetime.now(timezone.utc).isoformat());write_json(folder/'status.json',state)
        publish(folder,'failed');traceback.print_exc();return 1
    finally:lock.close()


if __name__=='__main__':sys.exit(main())
