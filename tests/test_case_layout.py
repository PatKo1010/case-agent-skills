import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import contextlib
import io

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.hermes/skills/pdf-ingest/scripts'))
import bundle
sys.path.insert(0,str(ROOT/'.hermes/skills/document-layout/scripts'))
from validate_document_layout import validate as validate_layout
sys.path.insert(0,str(ROOT/'.hermes/skills/document-structure/scripts'))
from validate_document_structure import validate as validate_structure
import build_document_structure
import locate_case


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.case=self.root/'output_fixture'
        for d in ('page','normalized','layout','structure','records'):
            (self.case/d).mkdir(parents=True,exist_ok=True)
        image=self.case/'page/page-1.png'; image.write_bytes(b'image')
        bundle.atomic(self.case/'manifest.json',{
            'source':'case.pdf','source_sha256':'source','status':'complete','page_count':1,'dpi':200,
            'pages':[{'page':1,'file':'page/page-1.png','sha256':bundle.sha(image),'width_px':1000,'height_px':1400}],
            'ocr_engine':{}
        })
        page={
            'document_id':'case','page':1,'image_sha256':bundle.sha(image),
            'image_width_px':1000,'image_height_px':1400,
            'raw_text':'Case Title\nEvidence','corrected_text':'Case Title\nEvidence',
            'blocks':[
                {'type':'paragraph','text':'Case Title','bbox':[100,50,700,120],'bbox_space':'rendered_image_px','confidence':1.0},
                {'type':'paragraph','text':'Evidence','bbox':[100,200,700,300],'bbox_space':'rendered_image_px','confidence':1.0},
            ],
            'uncertain_spans':[],'ocr_engine':None,'extraction_method':'native_text',
            'verification':'unverified','corrections':[]
        }
        bundle.atomic(self.case/'normalized/page-001.json',page)

    def test_ingest_bundle(self):
        bundle.validate_bundle(self.case)

    def test_layout_and_structure_binding(self):
        layout={
            'page':1,'image_sha256':bundle.read(self.case/'manifest.json')['pages'][0]['sha256'],
            'model_name':'PP-DocLayoutV2','model_version':'fixture','threshold':0.5,
            'regions':[
                {'id':'p001-r000','cls_id':1,'label':'document_title','score':0.95,'bbox':[90,40,720,130],'reading_order':0},
                {'id':'p001-r001','cls_id':2,'label':'text','score':0.95,'bbox':[90,190,720,320],'reading_order':1},
            ]
        }
        bundle.atomic(self.case/'layout/page-001.json',layout)
        bundle.atomic(self.case/'layout/layout_manifest.json',{
            'schema_version':1,'source_sha256':'source','model_name':'PP-DocLayoutV2',
            'paddleocr_version':'fixture','threshold':0.5,'pages':{'1':bundle.sha(self.case/'layout/page-001.json')}
        })
        validate_layout(self.case/'layout',self.case)
        # Structure builder is integration-tested manually with the real/model fixture;
        # validator should reject absent structure until it is built.
        with self.assertRaises(Exception):
            validate_structure(self.case/'structure',self.case)
        # The locator must finish at structure, without requiring semantic records.
        renamed = self.root/'output_source'
        self.case.rename(renamed)
        self.case = renamed
        with patch.object(locate_case, 'output_for', return_value=self.case):
            self.assertEqual(locate_case.inspect_case('case.pdf')['next_skill'], 'document-structure')
            with patch.object(sys, 'argv', ['build_document_structure.py', str(self.case)]), contextlib.redirect_stdout(io.StringIO()):
                build_document_structure.main()
            (self.case/'records').rmdir()
            result = locate_case.inspect_case('case.pdf')
            self.assertEqual(result['next_skill'], 'grounded-case-qa')
            self.assertTrue(result['qa_ready'])
            self.assertFalse((self.case/'records').exists())
            (self.case/'records').mkdir()
            (self.case/'records/events.jsonl').write_text('{invalid json')
            self.assertTrue(locate_case.inspect_case('case.pdf')['qa_ready'])
            # Required layers still block reuse if changed or missing.
            (self.case/'structure/blocks.jsonl').write_text('')
            result = locate_case.inspect_case('case.pdf')
            self.assertEqual(result['next_skill'], 'document-structure')
            self.assertFalse(result['qa_ready'])
            (self.case/'layout/layout_manifest.json').unlink()
            self.assertEqual(locate_case.inspect_case('case.pdf')['next_skill'], 'document-layout')
            (self.case/'normalized/page-001.json').unlink()
            self.assertEqual(locate_case.inspect_case('case.pdf')['next_skill'], 'pdf-ingest')


if __name__=='__main__':
    unittest.main()
