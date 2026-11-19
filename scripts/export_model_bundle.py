"""Validate/export six inference checkpoints, excluding training state and data."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from services.extractor.field_mapper import DOC_TYPE_TO_MODEL,LABEL_SETS

RUNTIME_FILES={'config.json','model.safetensors','processor_config.json','preprocessor_config.json',
    'tokenizer.json','tokenizer_config.json','special_tokens_map.json','added_tokens.json','vocab.json','merges.txt'}


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def inspect(root):
    root=Path(root).resolve();models={};files=[]
    for kind,name in DOC_TYPE_TO_MODEL.items():
        folder=root/name
        required={'config.json','model.safetensors','tokenizer_config.json'}
        if any(not (folder/f).is_file() for f in required):raise ValueError('Missing checkpoint files: '+name)
        if not any((folder/f).is_file() for f in ('processor_config.json','preprocessor_config.json')):raise ValueError('Missing image processor: '+name)
        if not (folder/'tokenizer.json').is_file() and not all((folder/f).is_file() for f in ('vocab.json','merges.txt')):raise ValueError('Missing tokenizer: '+name)
        config=json.loads((folder/'config.json').read_text(encoding='utf-8'))
        if [config['id2label'][str(i)] for i in range(len(LABEL_SETS[kind]))]!=LABEL_SETS[kind]:raise ValueError('Label schema mismatch: '+name)
        entries=[]
        for file in sorted(folder.iterdir()):
            if file.name not in RUNTIME_FILES:continue
            if file.is_symlink() or not file.is_file():raise ValueError('Runtime artifacts must be regular files')
            relative=file.relative_to(root).as_posix()
            entries.append(dict(path=relative,bytes=file.stat().st_size,sha256=sha(file)));files.append(file)
        models[kind]=dict(folder=name,files=entries)
    return dict(version=1,models=models,total_bytes=sum(e['bytes'] for m in models.values() for e in m['files'])),files


def verify(root):
    root=Path(root).resolve();manifest=json.loads((root/'model_bundle_manifest.json').read_text(encoding='utf-8'))
    if set(manifest['models'])!=set(DOC_TYPE_TO_MODEL):raise ValueError('Bundle must contain all six document types')
    for kind,model in manifest['models'].items():
        if model['folder']!=DOC_TYPE_TO_MODEL[kind]:raise ValueError('Wrong model folder')
        for entry in model['files']:
            path=(root/entry['path']).resolve()
            if not path.is_relative_to(root) or path.is_symlink() or not path.is_file():raise ValueError('Invalid bundle member')
            if path.stat().st_size!=entry['bytes'] or sha(path)!=entry['sha256']:raise ValueError('Bundle checksum mismatch: '+entry['path'])
    inspect(root)
    return manifest


def export(root,output):
    root=Path(root).resolve();output=Path(output).resolve()
    manifest,files=inspect(root)
    if output.exists():raise FileExistsError('Refusing to overwrite an existing release bundle')
    output.parent.mkdir(parents=True,exist_ok=True)
    # Weights compress poorly; stored ZIP is fast and supports files >4 GB.
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_STORED,allowZip64=True) as archive:
        for file in files:archive.write(file,file.relative_to(root).as_posix())
        archive.writestr('model_bundle_manifest.json',json.dumps(manifest,indent=2))
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-root',type=Path,required=True)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check-only',action='store_true');group.add_argument('--verify',action='store_true');group.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.verify:manifest=verify(args.model_root)
    elif args.output:manifest=export(args.model_root,args.output)
    else:manifest,_=inspect(args.model_root)
    print(json.dumps(dict(models=len(manifest['models']),total_bytes=manifest['total_bytes'],output=str(args.output) if args.output else None)))


if __name__=='__main__':main()
