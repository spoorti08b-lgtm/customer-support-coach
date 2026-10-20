"""Regenerates the synthetic sample PDFs in examples/sample_docs/.

All content is invented ("Acme Gadgets" does not exist). Needs no extra
packages; it reuses the tiny PDF writer from the test helpers.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from rag_test_support import write_pdf  # noqa: E402

OUT = Path(__file__).resolve().parent / "sample_docs"

DOCS = {
    "account_and_password_faq.pdf": [
        "ACME GADGETS - ACCOUNT FAQ (SAMPLE DATA)\n\n"
        "How do I reset my password?\n"
        "Open the sign-in page and select 'Forgot password'. Enter the email address on your account. "
        "We send a reset link that stays valid for 30 minutes. If no email arrives, check the spam folder "
        "and confirm that the address is spelled correctly.\n\n"
        "Why is my account locked?\n"
        "After five failed sign-in attempts the account is locked for 15 minutes. Waiting is usually "
        "enough; agents can also unlock it after verifying the customer's name and order number.",
        "How do I change my email address?\n"
        "Go to Settings, then Profile, and choose Change email. A confirmation code is sent to the new "
        "address. The old address keeps working until the code is confirmed.\n\n"
        "How do I enable two-step verification?\n"
        "Open Settings, then Security, and turn on two-step verification. Scan the QR code with an "
        "authenticator app and enter the six-digit code to finish setup.",
    ],
    "returns_and_refunds.pdf": [
        "ACME GADGETS - RETURNS AND REFUNDS POLICY (SAMPLE DATA)\n\n"
        "Return window\n"
        "Unused items can be returned within 30 days of delivery. Items must be in the original packaging "
        "with all accessories included. Software and gift cards cannot be returned once opened or redeemed.\n\n"
        "How refunds are issued\n"
        "Refunds go back to the original payment method within 5 to 7 business days after the warehouse "
        "receives the parcel. Shipping fees are refunded only when the item arrived damaged or was sent "
        "by mistake.\n\n"
        "Damaged or faulty items\n"
        "Report damage within 7 days and attach a photo. We offer a free replacement or a full refund, "
        "and we send a prepaid return label.",
    ],
    "shipping_and_delivery.pdf": [
        "ACME GADGETS - SHIPPING AND DELIVERY (SAMPLE DATA)\n\n"
        "Delivery times\n"
        "Standard delivery takes 3 to 5 business days. Express delivery takes 1 to 2 business days and is "
        "available for orders placed before 2 pm. Remote areas can add up to 3 extra days.\n\n"
        "Tracking your order\n"
        "A tracking number is emailed when the parcel leaves the warehouse. Tracking can take up to 24 "
        "hours to show its first update.",
        "Missing or delayed parcels\n"
        "If a parcel has not arrived 7 business days after dispatch, contact support with the order number. "
        "We open an investigation with the courier and either resend the order or refund it.\n\n"
        "Changing the delivery address\n"
        "The address can be changed only before the order is dispatched. After dispatch, ask the courier "
        "to redirect the parcel using the tracking number.",
    ],
}

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for name, pages in DOCS.items():
        write_pdf(OUT / name, pages)
        print("wrote", OUT / name)
