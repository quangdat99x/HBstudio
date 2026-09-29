"""Make Documentary Film: documentary projects built from the highlight database with Claude.

A project goes research -> script -> film. Each step, and every chat message, is one turn of a single
Claude Code session per project (resumed with --resume), run headless by DocFilmWorker. Every turn gets
the rulebook (RULEBOOK.md under the docfilm_root setting, history in docfilm_rules): the rules written
from the user's corrections, which Claude also updates when asked.
"""
