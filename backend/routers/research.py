"""Read-only measured benchmark artifacts; no endpoint launches paid work."""
import json
import re
from pathlib import Path
from fastapi import APIRouter,HTTPException
from fastapi.responses import FileResponse
from config import settings

router=APIRouter()


def latest_folder():
    root=Path(settings.RESEARCH_REPORT_DIR).resolve()
    index=root/'latest.json'
    if not index.is_file():return None
    identity=json.loads(index.read_text(encoding='utf-8'))['run_id']
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',identity):raise HTTPException(500,'Invalid research run index')
    return root/identity


@router.get('/research/latest')
def latest():
    folder=latest_folder()
    if folder is None:return {'status':'not_started','pipelines':{},'unavailable_metrics':[{'metric':'Benchmark results','reason':'No measured run is available yet.'}],'files':[]}
    summary=folder/'summary.json'
    result=json.loads(summary.read_text(encoding='utf-8')) if summary.exists() else {'status':'running','run_id':folder.name,'pipelines':{},'files':[]}
    progress=folder/'status.json'
    if progress.exists():result['progress']=json.loads(progress.read_text(encoding='utf-8'))
    checkpoints=folder/'checkpoints/summary.json'
    if checkpoints.exists():result['checkpoint_tests']=json.loads(checkpoints.read_text(encoding='utf-8'))
    pilot=folder/'pipelines/progress.json'
    if pilot.exists():result['pilot_progress']=json.loads(pilot.read_text(encoding='utf-8'))
    return result


@router.get('/research/files/{name}')
def artifact(name:str):
    if not re.fullmatch(r'[A-Za-z0-9_-]+\.(json|csv|md|png|svg)',name):raise HTTPException(404,'Artifact not found')
    folder=latest_folder()
    if folder is None:raise HTTPException(404,'No benchmark run')
    public={'summary.json','report.md','tables.csv'}
    if name not in public and not name.startswith('figure_'):raise HTTPException(404,'Artifact not published')
    path=(folder/name).resolve()
    if path.parent!=folder.resolve() or not path.is_file():raise HTTPException(404,'Artifact not found')
    return FileResponse(path,filename=name)
