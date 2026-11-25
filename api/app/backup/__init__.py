"""Backups (specs/016): encrypted snapshots of the database and the card images.

Runs only in the `backup` service and in one-off operator containers (constitution VII 1.4.0);
the app containers never mount the backup folder. Nothing here logs personal data or keys.
"""
