from services.extractor.ocr_compounds import normalize_compounds


def boxes(words):
    result=[];x=0
    for word in words:
        width=max(4,len(word)*5)
        result.append([[x,0],[x+width,0],[x+width,15],[x,15]]);x+=width+2
    return result


def test_identifier_preserves_every_character_and_source_mapping():
    words=['Invoice','No.', 'INV','/','24-25','/','00410']
    out,rects,sources=normalize_compounds(words,boxes(words))
    assert out==['Invoice','No.','INV/24-25/00410']
    assert sources[-1]==[2,3,4,5,6]
    assert rects[-1][0]==boxes(words)[2][0]


def test_handles_all_punctuation_split_and_dates():
    words=['GST','/','24','-','25','/','00625']
    assert normalize_compounds(words,boxes(words))[0]==['GST/24-25/00625']
    words=['02','-','Jul','-','2024']
    assert normalize_compounds(words,boxes(words))[0]==['02-Jul-2024']


def test_never_joins_across_rows_or_distant_columns():
    words=['INV','/','24-25','/','00410'];rects=boxes(words)
    rects[2]=[[70,100],[95,100],[95,115],[70,115]]
    assert normalize_compounds(words,rects)[0]==words
    rects=boxes(words);rects[1]=[[600,0],[605,0],[605,15],[600,15]]
    assert normalize_compounds(words,rects)[0]==words


def test_does_not_merge_caption_into_value_or_alter_complete_ids():
    for words in (['Invoice:','INV/24-25/00410'],['Acme','Business','Services'],['Total',':','1250.00']):
        assert normalize_compounds(words,boxes(words))[0]==words


def test_complete_identifier_is_not_extended_by_adjacent_number():
    words=['INV/24-25/00410','123']
    assert normalize_compounds(words,boxes(words))[0]==words


def test_field_assembly_removes_separator_spaces_but_preserves_names():
    from services.extractor.ocr_compounds import assemble_field_text
    assert assemble_field_text('invoice_no',['INV','/','24','-','25','/','00410'])=='INV/24-25/00410'
    assert assemble_field_text('invoice_date',['02','-','Jul','-','2024'])=='02-Jul-2024'
    assert assemble_field_text('vendor_name',['North','-','West','Services'])=='North - West Services'


def test_bio_assembler_restores_a_tagged_identifier_without_adding_characters():
    from services.extractor.layoutlm_extractor import _aggregate_bio_predictions
    words=['INV','/','24-25','/','00410']
    result=_aggregate_bio_predictions(words,[0,1,1,1,1],[.9]*5,list(range(5)),['B-INVOICE_NO','I-INVOICE_NO'])
    assert result['invoice_no'][0]=='INV/24-25/00410'
