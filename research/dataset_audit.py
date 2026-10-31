"""Exact split identity audit; does not claim to detect all near duplicates."""
import json
import sys
from collections import Counter,defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'layoutLM__model'))
from common import HERE,LABEL_SETS,read_rows,digest,write_json


def audit():
    folders={'funsd':HERE/'data/public/funsd','sroie':HERE/'data/public/sroie'}
    folders.update({t:HERE/'data/synthetic'/t.lower() for t in LABEL_SETS})
    report={}
    for name,folder in folders.items():
        hashes={};groups=defaultdict(set);collisions=[];counts={};manifests={};support=Counter()
        for split in ('train','development','test'):
            path=folder/(split+'.jsonl');rows=read_rows(path);counts[split]=len(rows);manifests[split]=digest(path)
            for row in rows:
                identity=digest(HERE/row['image'])
                if identity in hashes and hashes[identity][0]!=split:
                    collisions.append({'first_split':hashes[identity][0],'first_id':hashes[identity][1],'second_split':split,'second_id':row['id']})
                hashes[identity]=(split,row['id'])
                if row.get('group'):groups[row['group']].add(split)
                if split=='train':support.update(row['labels'])
        crossed={g:sorted(v) for g,v in groups.items() if len(v)>1}
        report[name]={'counts':counts,'manifest_sha256':manifests,'exact_image_cross_split_duplicates':collisions,
                      'groups_crossing_splits':crossed,'training_label_counts':dict(support),
                      'exact_split_audit_passed':not collisions and not crossed,
                      'scope':'Exact file hashes and declared groups only; no assertion that all near duplicates or template similarities are eliminated'}
    return report


if __name__=='__main__':
    result=audit();write_json(Path(sys.argv[1]),result)
    print(json.dumps({k:{'counts':v['counts'],'passed':v['exact_split_audit_passed']} for k,v in result.items()},indent=2))
