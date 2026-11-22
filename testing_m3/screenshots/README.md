# Screenshots

No screenshots were captured for this milestone, and none have been added
artificially.

To capture them yourself:

```bash
cd C:\Users\Admin\coding\customer-support-coach
streamlit run app.py
```

1. Open <http://localhost:8501>.
2. **Manual Mode:** choose Manual, fill product/scenario, start the session,
   paste a customer message, then screenshot the three panels.
3. **Replay Mode:** choose Replay, keep the bundled sample (or upload one of
   the files in `testing_m3/sample_transcripts/`), start, press **Next
   message** a few times, then screenshot the position indicator, replay
   controls and the coaching/knowledge panels.
4. Save the images in this folder with names such as
   `manual_mode_console.png` and `replay_mode_console.png`.

UI behaviour is otherwise verified automatically by `tests/test_m3_ui.py`
(Streamlit `AppTest`), which drives the real application.
