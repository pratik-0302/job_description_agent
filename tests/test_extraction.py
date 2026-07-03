import unittest
import os
import shutil
import tempfile
import datetime
from unittest.mock import MagicMock, patch

from src.config import AppConfig
from src.ingestion.models import ParsedDocument
from src.storage.sqlite_manager import SQLiteManager, DocumentRepository, MetadataRepository, JDMetadata, JDSkill, JDLocation, JDBranch, JDSelectionRound
from src.extraction.models import PartialMetadata, ExtractionReport
from src.extraction.rule_extractor import RuleBasedExtractor
from src.extraction.nlp_extractor import NLPExtractor
from src.extraction.llm_extractor import LLMExtractor
from src.extraction.metadata_extractor import MetadataExtractorModule


class TestExtractionLayer(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_metadata.db")
        self.db_manager = SQLiteManager(self.db_path)
        self.session = self.db_manager.get_session()
        
        self.doc_repo = DocumentRepository(self.session)
        self.meta_repo = MetadataRepository(self.session)
        
        self.cfg = AppConfig()
        self.cfg.paths.sqlite_db = self.db_path
        
        # Insert a mock document record in DB
        self.doc_id = "test-doc-id"
        self.doc_repo.insert_document({
            'doc_id': self.doc_id,
            'file_path': '/path/to/job.pdf',
            'file_name': 'job.pdf',
            'file_extension': '.pdf',
            'file_size_bytes': 2048,
            'content_hash': 'hash12345',
            'status': 'pending'
        })

    def tearDown(self):
        self.session.close()
        from src.storage.sqlite_manager import Base
        Base.metadata.drop_all(self.db_manager.engine)
        self.db_manager.engine.dispose()
        shutil.rmtree(self.test_dir)

    def test_rule_based_extractor(self):
        rule_extractor = RuleBasedExtractor()
        
        text = (
            "We are looking for candidates with a CGPA cutoff of 8.0 or above.\n"
            "The annual package CTC offered is 12 LPA.\n"
            "This is a remote work position.\n"
            "It is an internship of 6 months duration.\n"
            "The deadline to apply is 30 June 2026."
        )
        doc = ParsedDocument(
            doc_id=self.doc_id,
            file_path="/path/to/job.pdf",
            file_type="pdf",
            full_text=text
        )
        
        partial = rule_extractor.extract(doc)
        self.assertEqual(partial.cgpa_cutoff, 8.0)
        self.assertEqual(partial.package_ctc, 12.0)
        self.assertEqual(partial.work_mode, "remote")
        self.assertEqual(partial.duration_months, 6)
        self.assertEqual(partial.deadline, "30 June 2026")
        self.assertEqual(partial.job_type, "internship")

    def test_nlp_extractor(self):
        nlp_extractor = NLPExtractor()
        
        text = (
            "Required skills include Python, SQL, React and Docker.\n"
            "Open to students from Computer Science (CSE) and Electronics (ECE) branches.\n"
            "Work locations: Bangalore and Hyderabad.\n"
            "Requires 2+ years of relevant experience."
        )
        doc = ParsedDocument(
            doc_id=self.doc_id,
            file_path="/path/to/job.pdf",
            file_type="pdf",
            full_text=text
        )
        
        partial = PartialMetadata()
        partial = nlp_extractor.extract(doc, partial)
        
        self.assertIn("python", partial.required_skills)
        self.assertIn("react", partial.required_skills)
        self.assertIn("docker", partial.required_skills)
        self.assertIn("CSE", partial.eligible_branches)
        self.assertIn("ECE", partial.eligible_branches)
        self.assertIn("Bangalore", partial.location)
        self.assertIn("Hyderabad", partial.location)
        self.assertEqual(partial.experience_required, "2+ years of relevant experience")

    @patch('src.extraction.llm_extractor.ChatOllama')
    def test_llm_extractor(self, mock_chat_ollama):
        # Mock LLM invoke response content
        mock_response = MagicMock()
        mock_response.content = (
            '{\n'
            '  "company_name": "NVIDIA",\n'
            '  "role_title": "Hardware Intern",\n'
            '  "stipend_monthly": 50000.0,\n'
            '  "package_ctc": null,\n'
            '  "bond_clause": true,\n'
            '  "selection_process": ["Aptitude Test", "Technical Interview"],\n'
            '  "perks": ["Flexible hours", "Cab service"]\n'
            '}'
        )
        mock_chat_ollama.return_value.invoke.return_value = mock_response

        llm_extractor = LLMExtractor(self.cfg)
        
        doc = ParsedDocument(
            doc_id=self.doc_id,
            file_path="/path/to/job.pdf",
            file_type="pdf",
            full_text="Random text"
        )
        
        partial = PartialMetadata()
        missing = ["company_name", "role_title", "stipend_monthly", "bond_clause", "selection_process", "perks"]
        partial = llm_extractor.extract(doc, partial, missing)
        
        self.assertEqual(partial.company_name, "NVIDIA")
        self.assertEqual(partial.role_title, "Hardware Intern")
        self.assertEqual(partial.stipend_monthly, 50000.0)
        self.assertEqual(partial.bond_clause, True)
        self.assertIn("Flexible hours", partial.perks)
        self.assertIn("Aptitude Test", partial.selection_process)

    def test_metadata_repository_persistence(self):
        meta_data = {
            'company_name': 'Microsoft',
            'role_title': 'SWE',
            'job_type': 'fte',
            'package_ctc': 44.0,
            'cgpa_cutoff': 8.5,
            'eligible_branches': ['CSE', 'IT'],
            'required_skills': ['C++', 'Algorithms'],
            'location': ['Bangalore'],
            'work_mode': 'hybrid',
            'bond_clause': False,
            'deadline': '2026-07-20',
            'selection_process': ['Coding Round', 'System Design']
        }
        
        # Insert
        meta = self.meta_repo.insert_metadata(self.doc_id, meta_data)
        self.assertIsNotNone(meta)
        self.assertEqual(meta.company_name, 'Microsoft')
        
        # Verify related entries in child tables
        skills = self.session.query(JDSkill).filter(JDSkill.doc_id == self.doc_id).all()
        self.assertEqual(len(skills), 2)
        self.assertTrue(any(s.skill == 'C++' for s in skills))
        
        branches = self.session.query(JDBranch).filter(JDBranch.doc_id == self.doc_id).all()
        self.assertEqual(len(branches), 2)
        
        rounds = self.session.query(JDSelectionRound).filter(JDSelectionRound.doc_id == self.doc_id).all()
        self.assertEqual(len(rounds), 2)
        self.assertEqual(rounds[0].round_name, 'Coding Round')
        
        # Delete Metadata
        self.meta_repo.delete_metadata(self.doc_id)
        
        # Verify Cascade
        meta_lookup = self.meta_repo.get_metadata(self.doc_id)
        self.assertIsNone(meta_lookup)
        
        # Check child tables are cleaned up
        skills_lookup = self.session.query(JDSkill).filter(JDSkill.doc_id == self.doc_id).all()
        self.assertEqual(len(skills_lookup), 0)

    @patch('src.extraction.llm_extractor.ChatOllama')
    def test_coordinator_module(self, mock_chat_ollama):
        mock_response = MagicMock()
        mock_response.content = '{"company_name": "Google", "role_title": "SWE", "bond_clause": false, "selection_process": []}'
        mock_chat_ollama.return_value.invoke.return_value = mock_response

        text = (
            "Google is hiring software engineers for Bangalore.\n"
            "CGPA criteria: 8.5\n"
            "Skills required: Python, SQL"
        )
        doc = ParsedDocument(
            doc_id=self.doc_id,
            file_path="/path/to/job.pdf",
            file_type="pdf",
            full_text=text
        )
        
        coordinator = MetadataExtractorModule(self.cfg)
        normalized_data, report = coordinator.extract_metadata(doc)
        
        self.assertEqual(normalized_data['company_name'], "Google")
        self.assertEqual(normalized_data['cgpa_cutoff'], 8.5)
        self.assertIn("python", normalized_data['required_skills'])
        self.assertIn("Bangalore", normalized_data['location'])
        self.assertEqual(report.llm_called, True)


if __name__ == "__main__":
    unittest.main()
