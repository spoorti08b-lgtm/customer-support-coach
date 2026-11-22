"""Manual Mode and Replay Mode support (Infosys Milestone 3).

This package holds the Streamlit-free logic behind the two coaching modes so
it can be unit- and integration-tested without starting the UI:

* :mod:`backend.modes.transcripts` - upload validation and JSON/CSV/TXT
  transcript parsing for Replay Mode.
* :mod:`backend.modes.coaching` - bridges both modes to the existing
  Intent & Sentiment Analysis Agent, the knowledge base and the coaching
  helpers, and normalises everything into one analysis dictionary.
* :mod:`backend.modes.manual` - session-safe customer/agent turn submission
  with validation, duplicate prevention and session isolation.
* :mod:`backend.modes.replay` - deterministic replay position management
  (start/pause/resume/next/previous/restart) with cached per-message
  analysis so stepping backwards never duplicates turns.
"""

__all__ = ["coaching", "manual", "replay", "transcripts"]
