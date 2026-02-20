# EnrollmentOS

## Tracking task progress with the agent

If you want visibility into how much work is left, ask for updates in this format:

- **Plan**: short checklist of remaining steps.
- **Current step**: exactly what is being worked on now.
- **Estimated remaining steps**: count of unfinished items.
- **Blockers**: anything preventing completion.

Example request you can send:

> "Before each change, show me: (1) completed steps, (2) current step, (3) remaining steps, and (4) what could change the estimate."

This gives you clear progress without exposing private chain-of-thought details.


## Staff assessment survey

Run the staff rubric survey app with:

```bash
streamlit run staff_survey.py
```


## Quick start (I set this up for you)

From the repo root, run one of these:

```bash
./run_staff_survey.sh
./run_dashboard.sh
```

These scripts create a local `.venv`, install dependencies from `requirements.txt`, and launch Streamlit.
