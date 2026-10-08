# Maintenance repair: aw-maint-fault-001

- Binding: b152041300c694178936355ffa9acc8a9
- Notification aw-maint-task-001 received; ACK state: published.
- Original operation before repair: pending message from sentinel to steward.
- Initial doctor: degraded; publication_pending for sentinel / aw-maint-fault-001.
- Repair request aw-maint-repair-001: repair.state=applied; result.state=published.
- Follow-up operation: published. Follow-up doctor: healthy; issues empty. Target publication_pending disappeared.
- Limitation: confirms publication reconciliation and doctor state only, not steward receipt or processing. One unacknowledged notification remains for steward.