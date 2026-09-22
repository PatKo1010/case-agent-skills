import argparse
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.hermes/skills/pdf-scan-ingest/scripts'))
import bundle
import locate_case
import ingest_pdf
from validate_case_records import validate_records


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pdf = self.root / 'case.pdf'
        self.pdf.write_bytes(b'fixture')
        mock = patch.object(bundle, '__file__', str(self.root / '.hermes/skills/pdf-scan-ingest/scripts/bundle.py'))
        mock.start()
        self.addCleanup(mock.stop)

    def test_content_address_not_filename(self):
        renamed = self.root / 'renamed.pdf'
        renamed.write_bytes(self.pdf.read_bytes())
        self.assertEqual(bundle.output_for(self.pdf), bundle.output_for(renamed))
        renamed.write_bytes(b'changed')
        self.assertNotEqual(bundle.output_for(self.pdf), bundle.output_for(renamed))

    def test_cached_qa_and_stale_index_routing(self):
        out = bundle.output_for(self.pdf)
        self.assertEqual(locate_case.inspect_case(self.pdf)['next_skill'], 'pdf-scan-ingest')
        self.assertFalse(out.exists())
        for name in ('page', 'ocr', 'records'):
            (out / name).mkdir(parents=True, exist_ok=True)
        image = out / 'page/page-1.png'
        image.write_bytes(b'fixture image')
        page = {'document_id': 'case', 'page': 1, 'image_sha256': bundle.sha(image),
                'raw_text': 'Evidence', 'corrected_text': 'Evidence', 'blocks': [],
                'uncertain_spans': [], 'ocr_engine': {}, 'verification': 'unverified', 'corrections': []}
        bundle.atomic(out / 'manifest.json', {'source_sha256': bundle.sha(self.pdf), 'status': 'complete',
                      'page_count': 1, 'ocr_engine': {}, 'pages': [{'page': 1, 'file': 'page/page-1.png', 'sha256': bundle.sha(image)}]})
        bundle.atomic(out / 'ocr/page-001.json', page)
        self.assertEqual(locate_case.inspect_case(self.pdf)['next_skill'], 'case-record-structure')
        records = out / 'records'
        row = {'id': 'doc-1', 'kind': 'document', 'attributes': {}, 'source_pages': [1],
               'source_quote': 'Evidence', 'confidence': .9, 'verification': 'unverified'}
        (records / 'documents.jsonl').write_text(json.dumps(row)+'\n')
        for name in ('entities', 'events', 'evidence'):
            (records / f'{name}.jsonl').write_text('')
        (records / 'case_summary.md').write_text('Evidence (page 1)')
        _, binding = validate_records(records, out, check_binding=False)
        bundle.atomic(records / 'index_manifest.json', binding)
        self.assertEqual(locate_case.inspect_case(self.pdf)['next_skill'], 'grounded-case-qa')
        page['uncertain_spans'] = [{'text': 'Evidence', 'reason': 'review'}]
        bundle.atomic(out / 'ocr/page-001.json', page)
        self.assertEqual(locate_case.inspect_case(self.pdf)['next_skill'], 'case-record-structure')
        image.write_bytes(b'corrupt')
        self.assertEqual(locate_case.inspect_case(self.pdf)['next_skill'], 'pdf-scan-ingest')

    def test_ingest_layout_and_resume(self):
        import pymupdf
        doc = pymupdf.open()
        doc.new_page()
        doc.new_page()
        doc.save(self.pdf)
        doc.close()
        model = self.root / 'model'
        model.mkdir()
        for name in ('inference.json', 'inference.pdiparams', 'inference.yml'):
            (model / name).write_text('fixture')
        args = argparse.Namespace(pdf=self.pdf, output=bundle.output_for(self.pdf), det_model_dir=model,
                                  rec_model_dir=model, resume=False, uncertain_threshold=.9)
        seen = []
        class OCR:
            fail = True
            def __init__(self, **kwargs): pass
            def predict(self, path):
                seen.append(Path(path).name)
                if self.fail and len(seen) == 2:
                    raise TimeoutError('interruption')
                return [{'rec_texts': ['text'], 'rec_scores': [.9], 'rec_boxes': [[0,0,1,1]]}]
        with patch('ingest_pdf.importlib.metadata.version', return_value='fixture'), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(TimeoutError): ingest_pdf.run(args, OCR)
            args.resume = True
            OCR.fail = False
            seen.clear()
            ingest_pdf.run(args, OCR)
        self.assertEqual(seen, ['page-2.png'])
        self.assertEqual({p.name for p in args.output.iterdir() if p.is_dir()}, {'page', 'ocr', 'records'})
        self.assertTrue((args.output / 'job.json').is_file())
        bundle.validate_bundle(args.output)
        # Re-entering the CLI with valid OCR must not load models or require weights.
        with patch.object(sys, 'argv', ['ingest_pdf.py', str(self.pdf)]), patch.object(ingest_pdf, 'run', side_effect=AssertionError('must reuse')), contextlib.redirect_stdout(io.StringIO()):
            ingest_pdf.main()

if __name__ == '__main__':
    unittest.main()
