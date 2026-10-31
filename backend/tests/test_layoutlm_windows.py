"""Long-document inference must retain fields outside the first token window."""
from types import SimpleNamespace
import io
import json
import torch
from PIL import Image
from config import settings
from services.extractor import layoutlm_extractor


def test_layoutlm_merges_overlapping_windows_without_losing_last_field(tmp_path,monkeypatch):
    class Encoding(dict):
        def word_ids(self,batch_index=0):
            return [[None,0,1,None],[None,1,2,None]][batch_index]
    class Processor:
        def __call__(self,*args,**kwargs):
            assert kwargs["stride"]==96 and kwargs["return_overflowing_tokens"]
            return Encoding(input_ids=torch.tensor([[0,1,2,0],[0,2,3,0]]),
                attention_mask=torch.ones((2,4),dtype=torch.long),bbox=torch.zeros((2,4,4),dtype=torch.long),
                pixel_values=torch.zeros((2,3,224,224)),offset_mapping=torch.zeros((2,4,2),dtype=torch.long))
    class Model:
        def __call__(self,**inputs):
            ids=inputs["input_ids"][0]
            logits=torch.zeros((1,len(ids),3))
            for i,identity in enumerate(ids.tolist()):
                logits[0,i,{0:0,1:1,2:0,3:2}[identity]]=10
            return SimpleNamespace(logits=logits)
    monkeypatch.setattr(settings,"LAYOUTLM_MODEL_ROOT",str(tmp_path))
    folder=tmp_path/"layoutlm-synthetic-tax_invoice-trained"
    folder.mkdir();(folder/"config.json").write_text(json.dumps({}))
    monkeypatch.setattr(layoutlm_extractor,"_get_model_for_doc_type",lambda *a:(Processor(),Model(),["O","B-INVOICE_NO","B-TOTAL_AMOUNT"]))
    stream=io.BytesIO();Image.new("RGB",(100,100)).save(stream,format="PNG")
    diagnostics={}
    fields=layoutlm_extractor.extract_fields(stream.getvalue(),["INV-1","text","100.00"],
        [[[0,0],[5,0],[5,5],[0,5]]]*3,100,100,"GST_INVOICE","INV-1 text 100.00",strict=True,diagnostics=diagnostics)
    assert {f["key"]:f["value"] for f in fields}=={"invoice_no":"INV-1","total_amount":"100.00"}
    assert diagnostics["window_count"]==2 and diagnostics["encoded_words"]==3 and not diagnostics["truncated"]
