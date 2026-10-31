import sys
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import HERE,LABEL_SETS,validate_row
from prepare_public import split_training
from synthetic import render,TITLES
from train_stage import entity_spans,enable_checkpointing,reset_head


def test_public_development_split_never_overlaps_training():
    rows=[{"id":str(n)} for n in range(100)]
    train,dev=split_training(rows)
    assert len(train)==85 and len(dev)==15
    assert not ({r["id"] for r in train}&{r["id"] for r in dev})
    assert split_training(rows)==(train,dev)


@pytest.mark.parametrize("doc_type",list(TITLES))
def test_generator_schema_and_disjoint_family_groups(doc_type):
    # Kept under ignored generated-data root, not beside versioned source.
    destination=HERE/"data/contract-tests"
    train=render(doc_type,1,0,"train",destination)
    test=render(doc_type,34,0,"test",destination)
    assert train["group"]!=test["group"]
    for row in (train,test):
        validate_row(row,LABEL_SETS[doc_type])
        assert set(row["fields"])=={label[2:].lower() for label in LABEL_SETS[doc_type] if label.startswith("B-")}
        reconstructed={name.lower():text for name,_,_,text in entity_spans(row["words"],row["labels"])}
        assert reconstructed=={k:v for k,v in row["fields"].items() if v is not None}


def test_invalid_inside_label_fails_audit():
    with pytest.raises(ValueError,match="BIO continuation"):
        validate_row(dict(id="bad",words=["test"],boxes=[[0,0,10,10]],labels=["I-QUESTION"]),["O","B-QUESTION","I-QUESTION"])


def test_layer_checkpointing_preserves_gradients():
    import copy
    from types import SimpleNamespace
    import torch
    original=torch.nn.Linear(4,4)
    wrapped=copy.deepcopy(original)
    model=SimpleNamespace(layoutlmv3=SimpleNamespace(encoder=SimpleNamespace(layer=[wrapped])))
    enable_checkpointing(model)
    x=torch.randn(2,4,requires_grad=True)
    original(x).sum().backward()
    wrapped(x.detach().clone().requires_grad_(True)).sum().backward()
    assert torch.allclose(original.weight.grad,wrapped.weight.grad)
    assert torch.allclose(original.bias.grad,wrapped.bias.grad)


def test_replacement_head_supports_linear_and_mlp_without_touching_encoder():
    import torch
    from types import SimpleNamespace
    for head in (torch.nn.Linear(4,7),torch.nn.Sequential(torch.nn.Linear(4,4),torch.nn.Tanh(),torch.nn.Linear(4,27))):
        for parameter in head.parameters():
            torch.nn.init.constant_(parameter,7)
        encoder=torch.nn.Linear(4,4)
        before=encoder.weight.detach().clone()
        reset_head(SimpleNamespace(classifier=head,layoutlmv3=encoder))
        assert all(not torch.all(parameter==7) for parameter in head.parameters())
        assert torch.equal(before,encoder.weight)
