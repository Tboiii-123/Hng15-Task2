import logging

import httpx

from app import config

log = logging.getLogger("shop.email")


def money(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def build_order_email(order) -> tuple[str, str, str]:
    rows_text = "\n".join(
        f"- {i.quantity} x {i.name}  "
        f"{money(i.unit_price_cents * i.quantity)}"
        for i in order.items
    )

    rows_html = "".join(
        f"<tr>"
        f"<td>{i.quantity} &times; {i.name}</td>"
        f"<td style='text-align:right'>"
        f"{money(i.unit_price_cents * i.quantity)}"
        f"</td>"
        f"</tr>"
        for i in order.items
    )

    subject = f"Order #{order.id} confirmed"

    text = (
        f"Hi {order.full_name},\n\n"
        f"Thanks for your order #{order.id}!\n\n"
        f"{rows_text}\n\n"
        f"Total: {money(order.total_cents)}\n\n"
        f"Shipping to:\n"
        f"{order.address}, {order.city}\n"
    )

    html = (
        f"<h2>Thanks for your order, {order.full_name}!</h2>"
        f"<p>Order <b>#{order.id}</b> is confirmed.</p>"
        f"<table width='100%' cellpadding='6'>"
        f"{rows_html}"
        f"<tr>"
        f"<td><b>Total</b></td>"
        f"<td style='text-align:right'>"
        f"<b>{money(order.total_cents)}</b>"
        f"</td>"
        f"</tr>"
        f"</table>"
        f"<p>"
        f"Shipping to:<br>"
        f"{order.address}, {order.city}"
        f"</p>"
    )

    return subject, text, html


def send_order_confirmation(order_id: int) -> None:
    """Runs as a background task: emails the customer, then records the result."""

    from app.database import SessionLocal
    from app.models import Order

    db = SessionLocal()

    try:
        order = db.get(Order, order_id)

        if order is None:
            log.warning(
                "Order %s not found; skipping confirmation email",
                order_id,
            )
            return

        # Check Mailgun configuration
        if not config.MAILGUN_API_KEY or not config.MAILGUN_DOMAIN:
            log.warning(
                "Mailgun not configured; skipping email for order %s",
                order_id,
            )
            return

        subject, text, html = build_order_email(order)

        try:
            resp = httpx.post(
                f"{config.MAILGUN_API_BASE}/v3/"
                f"{config.MAILGUN_DOMAIN}/messages",
                auth=("api", config.MAILGUN_API_KEY),
                data={
                    "from": (
                        config.MAILGUN_FROM
                        or f"Shop <postmaster@{config.MAILGUN_DOMAIN}>"
                    ),
                    "to": [order.email],
                    "subject": subject,
                    "text": text,
                    "html": html,
                },
                timeout=15,
            )

            # Log Mailgun's actual response when something goes wrong.
            if resp.is_error:
                log.error(
                    "Mailgun send failed for order %s: "
                    "status=%s response=%s",
                    order_id,
                    resp.status_code,
                    resp.text,
                )

                resp.raise_for_status()

            # Only mark the email as sent after Mailgun succeeds.
            order.email_sent = True
            db.commit()

            log.info(
                "Order confirmation email sent successfully "
                "for order %s to %s",
                order_id,
                order.email,
            )

        except httpx.HTTPStatusError as exc:
            log.error(
                "Mailgun returned an HTTP error for order %s: "
                "status=%s response=%s",
                order_id,
                exc.response.status_code,
                exc.response.text,
            )

        except httpx.RequestError as exc:
            log.error(
                "Mailgun request failed for order %s: %s",
                order_id,
                exc,
            )

        except httpx.HTTPError as exc:
            log.error(
                "Mailgun HTTP error for order %s: %s",
                order_id,
                exc,
            )

    finally:
        db.close()
