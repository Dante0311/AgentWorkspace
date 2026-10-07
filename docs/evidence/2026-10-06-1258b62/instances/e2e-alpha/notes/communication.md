# Communication record

- Current binding: `b89818d3a91bf4545b646a68571aaf6b8`.
- Sent request: `m-e2e-luna-request-001` to e2e-beta.
- Received reply: `m-e2e-luna-reply-001` from e2e-beta; it references `m-e2e-luna-request-001`.
- Verified marker in reply: `AW-E2E-d723faeb0af548dab83cadb7b8327110`.
- Actual reply content: “M test reply: received marker AW-E2E-d723faeb0af548dab83cadb7b8327110 and acknowledged the original notification.”
- ACK: receiving the reply published `ack-m-e2e-luna-reply-001` for `m-e2e-luna-reply-001`; state `published`, receiver e2e-alpha, binding above.
- Historical inconsistency: preserve older `e2e-alpha-second-stop-001` as submitted/unknown; it was not replayed.
