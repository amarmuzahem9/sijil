"""One import confirmation at a time, across workers and across import kinds (specs/014 research
R10, specs/015 research R12): the legacy and the SAS confirmations take the same transaction-level
advisory lock."""

IMPORT_CONFIRM_LOCK = 140_014
