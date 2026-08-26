"""Provider adapter interface for channel connectors.

app/execution/connectors.py decides *whether* an attempt succeeds by
rolling against the hidden recoverability model - that's the simulation.
This module is the seam where a real dispatch would happen: handing the
message off to an actual SMS/voice/email/WhatsApp API. Swapping in a real
provider later means implementing ChannelProvider once, not touching the
runner or the recoverability model.

LoggingChannelProvider is the only implementation for this build - it
logs a structured "sent" record and returns a synthetic receipt id,
standing in for whatever a real provider's API response would carry
(Twilio's SID, Razorpay's communication id, etc).
"""
import logging
import uuid
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderReceipt:
    provider: str
    receipt_id: str
    status: str  # "sent" | "failed" - this mock never fails; a real one could


class ChannelProvider(Protocol):
    def send(self, *, channel: str, action: str, case_id: uuid.UUID, customer_id: uuid.UUID) -> ProviderReceipt: ...


class LoggingChannelProvider:
    """Stand-in for a real SMS/voice/email/WhatsApp API. Every dispatch is
    logged as a structured record and given a synthetic receipt id -
    exactly the shape a real provider integration would need to carry
    through to the Attempt/AuditEvent for later reconciliation.
    """

    name = "logging_mock"

    def send(self, *, channel: str, action: str, case_id: uuid.UUID, customer_id: uuid.UUID) -> ProviderReceipt:
        receipt = ProviderReceipt(provider=self.name, receipt_id=f"mock_{uuid.uuid4().hex[:16]}", status="sent")
        logger.info(
            "channel_provider_send",
            extra={
                "provider": receipt.provider,
                "receipt_id": receipt.receipt_id,
                "channel": channel,
                "action": action,
                "case_id": str(case_id),
                "customer_id": str(customer_id),
            },
        )
        return receipt


default_provider: ChannelProvider = LoggingChannelProvider()
