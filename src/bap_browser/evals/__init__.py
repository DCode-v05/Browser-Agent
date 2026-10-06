"""Evaluations of the browsers of the window (spec 12.6): what each one's tasks took and cost, how
they ended, the trace of each, and a checklist of real steps."""

from bap_browser.evals.record import Outcome, Rating, Recorder, Trace
from bap_browser.evals.summary import summarise, trace_of

__all__ = ["Outcome", "Rating", "Recorder", "Trace", "summarise", "trace_of"]
