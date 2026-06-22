# parser

Korean law document parsing utilities.

## Purpose
Parses Korean legal PDFs into structured data for Neo4j ingestion.
Works with `law/` pipeline for the full PDF-to-graph flow.

## Note
NOT a Django app. Standalone Python utility package.
The actual law search API is at `AG/agent/law-domain-agents/` (port 8011).
