import importlib.util
import json
from pathlib import Path
import zipfile
import pytest

spec=importlib.util.spec_from_file_location('bundle',Path(__file__).resolve().parents[1]/'export_model_bundle.py')
bundle=importlib.util.module_from_spec(spec);spec.loader.exec_module(bundle)


def fixtures(root):
    for kind,name in bundle.DOC_TYPE_TO_MODEL.items():
        folder=root/name;folder.mkdir(parents=True)
        (folder/'config.json').write_text(json.dumps(dict(id2label=dict(enumerate(bundle.LABEL_SETS[kind])))),encoding='utf-8')
        for file in ('model.safetensors','tokenizer_config.json','processor_config.json','tokenizer.json'):(folder/file).write_bytes(b'fixture')
        (folder/'last.pt').write_bytes(b'do not export')
        (folder/'training_provenance.json').write_text('private local paths',encoding='utf-8')


def test_bundle_contains_runtime_only_and_verifies_hashes(tmp_path):
    root=tmp_path/'models';fixtures(root);archive=tmp_path/'release.zip'
    result=bundle.export(root,archive)
    assert len(result['models'])==6
    with zipfile.ZipFile(archive) as z:
        assert not any(name.endswith(('last.pt','training_provenance.json')) for name in z.namelist())
        z.extractall(tmp_path/'restored')
    bundle.verify(tmp_path/'restored')
    target=tmp_path/'restored'/next(iter(bundle.DOC_TYPE_TO_MODEL.values()))/'model.safetensors'
    target.write_bytes(b'corrupted')
    with pytest.raises(ValueError,match='checksum mismatch'):bundle.verify(tmp_path/'restored')


def test_missing_checkpoint_blocks_export(tmp_path):
    with pytest.raises(ValueError,match='Missing checkpoint'):bundle.export(tmp_path,tmp_path/'release.zip')
    assert not (tmp_path/'release.zip').exists()
