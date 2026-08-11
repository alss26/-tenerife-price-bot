import os, re, json
from pathlib import Path
from datetime import datetime, timezone

import resend
from playwright.sync_api import sync_playwright

URL = "https://www.wizzair.com/en-gb/booking/select-flight/OTP/TFS/2026-11-23/2026-12-03/1/0/0/null"
HISTORY = Path("data/history.json")
HISTORY.parent.mkdir(exist_ok=True)


def prices_from(text):
    found = []

    for pattern in [
        r"RON\s*([0-9][0-9 .]*)",
        r"([0-9][0-9 .]*)\s*RON",
        r"([0-9][0-9 .]*)\s*(?:lei|LEI)"
    ]:
        for value in re.findall(pattern, text, re.I):
            try:
                number = float(value.replace(" ", "").replace(".", ""))

                if 50 <= number <= 5000:
                    found.append(number)

            except Exception:
                pass

    return sorted(set(found))


# --------------------------------------------------
# VERIFICARE WIZZ AIR
# --------------------------------------------------

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    page = browser.new_page(locale="en-GB")

    page.goto(
        URL,
        wait_until="domcontentloaded",
        timeout=90000
    )

    page.wait_for_timeout(12000)

    text = page.locator("body").inner_text(timeout=20000)

    browser.close()


prices = prices_from(text)

if not prices:
    raise RuntimeError(
        "Nu am gasit un pret RON pe pagina Wizz."
    )


price = prices[0]


# --------------------------------------------------
# ISTORIC PRETURI
# --------------------------------------------------

history = (
    json.loads(HISTORY.read_text())
    if HISTORY.exists()
    else []
)

previous = (
    history[-1]["price_ron"]
    if history
    else None
)

minimum = min(
    [x["price_ron"] for x in history] + [price]
)


history.append({
    "checked_at": datetime.now(timezone.utc).isoformat(),
    "price_ron": price
})

HISTORY.write_text(
    json.dumps(
        history[-180:],
        ensure_ascii=False,
        indent=2
    )
)


# --------------------------------------------------
# VERDICT
# --------------------------------------------------

verdict = (
    "CUMPARA - pret foarte bun"
    if price <= 600
    else
    "PRET BUN"
    if price <= 750
    else
    "ASTEAPTA"
)


change = (
    "prima verificare"
    if previous is None
    else f"{price - previous:+.0f} RON fata de ultima verificare"
)


body = f"""Wizz Air - Bucuresti -> Tenerife

23 noiembrie 2026 -> 3 decembrie 2026

Pret detectat: {price:.0f} RON
Schimbare: {change}
Minim in istoricul botului: {minimum:.0f} RON

Verdict: {verdict}

{URL}
"""


print(body)


# --------------------------------------------------
# TRIMITERE EMAIL PRIN RESEND
# --------------------------------------------------

if os.getenv("RESEND_API_KEY"):

    resend.api_key = os.environ["RESEND_API_KEY"]

    email = resend.Emails.send({
        "from": os.environ["RESEND_FROM"],
        "to": [os.environ["ALERT_TO"]],
        "subject": f"Tenerife Wizz: {price:.0f} RON - {verdict}",
        "text": body
    })

    print("Email trimis prin Resend.")
    print(email)
else:
    print(
        "RESEND_API_KEY nu este configurata. "
        "Emailul nu a fost trimis."
    )
