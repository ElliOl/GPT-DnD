"""
Content sources.

``backend/adventures/`` holds the canonical module JSON and is read-only. The
Story Architect (phase 6) writes generated packs into ``generated/{campaign_id}/``
using that same schema, and a merged loader overlays generated content on
canonical. Generating content into the existing format is what makes
improvisation cost nothing extra at runtime.
"""
