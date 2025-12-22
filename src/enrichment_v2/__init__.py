"""
DPC Enrichment System V2

A comprehensive, production-grade enrichment system for Direct Primary Care practices.

Features:
- Multi-threaded async scraping with 4 fallback methods
- Multi-page crawling (up to 15 pages per practice)
- Markdown conversion with 4 fallback methods
- Gemini 2.5 Flash Preview AI for field extraction
- Circuit breakers and retry mechanisms
- Progress tracking and resumability
- Complete storage systems for markdown and JSON

Usage:
    from enrichment_v2.orchestrator import EnrichmentOrchestrator

    orchestrator = EnrichmentOrchestrator(
        openrouter_api_key="YOUR_KEY",
        input_file="data/processed/dpc_complete.json",
        output_file="data/enriched/dpc_enriched_v2.json",
        markdown_dir="data/markdown",
        progress_file="data/progress/state.json"
    )

    stats = await orchestrator.run()
"""

__version__ = '2.0.0'
__author__ = 'DPC Directory'

from .orchestrator import EnrichmentOrchestrator
from .config import *

__all__ = ['EnrichmentOrchestrator']
