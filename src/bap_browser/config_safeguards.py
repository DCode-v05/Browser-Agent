"""The settings of Auto Mode, the safeguards and the limits (spec 18.11), with their defaults.

They are part of the configuration: `config.py` holds them in `safety.auto_mode`, `safeguards` and
`limits`. They are in a file of their own because one file would be too long to read.
"""

from __future__ import annotations

from typing import Literal

from bap_browser.config_base import Section, setting


class AutoMode(Section):
    offered: bool = setting(False, "Whether a person may choose `auto` for `safety.ask_before`")
    refusals_in_a_row: int = setting(3, "Refusals by the check in a row after which Auto Mode pauses")
    refusals_per_session: int = setting(20, "Refusals by the check in one session after which it pauses")
    steps_shown: int = setting(12, "The earlier steps the check's model is given")
    earlier_tasks_shown: int = setting(3, "The earlier messages of the person the check's model is given")
    allow_once_s: int = setting(300, 'How long "Allow once" holds for the step it was pressed for')


class CheckModel(Section):
    name: str = setting("", "The model of the reviewer and the scan. Empty means `agent.model`")
    timeout_s: int = setting(8, "Longest wait for one answer. A step waits for it")
    max_tokens: int = setting(1500, "The most one answer may be, its reasoning counted")
    reasoning_effort: Literal["", "none", "minimal", "low", "medium", "high"] = setting(
        "low", "How much the model thinks before it answers. Empty sends no such setting"
    )
    retries: int = setting(1, "Further tries of a failed call")
    backoff_base_ms: int = setting(500, "The wait before the second try. It doubles with each try")
    backoff_max_ms: int = setting(8000, "The longest wait between two tries")
    retry_after_max_s: int = setting(30, "The longest wait the provider may ask for")
    breaker_failures: int = setting(3, "Failed calls in a row after which no call is made for a while")
    breaker_cooldown_s: int = setting(60, "How long no call is made then")
    input_price_per_million: float | None = setting(
        None, "What a million tokens sent to this model cost. None means the agent's price"
    )
    output_price_per_million: float | None = setting(
        None, "What a million tokens this model wrote cost. None means the agent's price"
    )


class ReviewerShown(Section):
    name_chars: int = setting(80, "How much of a control's name the check's model is given")
    typed_chars: int = setting(200, "How much of the text a step types")
    address_chars: int = setting(300, "How much of an address")
    sample_chars: int = setting(80, "How much of text that was copied from another site")
    reason_chars: int = setting(120, "How much of the model's own reason is kept, and shown to a person")


class Actions(Section):
    pays: list[str] = setting(
        [
            "pay",
            "pays",
            "paying",
            "payment",
            "buy",
            "buying",
            "purchase",
            "order",
            "checkout",
            "check out",
            "place order",
            "book now",
            "reserve",
            "donate",
            "subscribe",
            "transfer",
            "top up",
            "भुगतान",
            "खरीदें",
            "ऑर्डर करें",
            "बुक करें",
        ],
        "A control whose name holds one of these pays",
    )
    sends: list[str] = setting(
        [
            "send",
            "sent",
            "sending",
            "post",
            "submit",
            "publish",
            "tweet",
            "भेजें",
            "पोस्ट करें",
            "जमा करें",
            "सबमिट",
        ],
        "A control whose name holds one of these sends something to other people",
    )
    deletes: list[str] = setting(
        [
            "delete",
            "deleting",
            "remove",
            "erase",
            "discard",
            "clear all",
            "cancel order",
            "unsubscribe",
            "deactivate",
            "close account",
            "हटाएं",
            "हटाएँ",
            "मिटाएं",
            "रद्द करें",
        ],
        "A control whose name holds one of these deletes",
    )
    grants: list[str] = setting(
        ["authorize", "authorise", "grant", "grant access", "allow access"],
        "A control whose name holds one of these gives access",
    )
    commits: list[str] = setting(
        ["confirm", "पुष्टि करें"],
        "A control whose name holds one of these makes something final",
    )
    message_words: list[str] = setting(
        ["message", "comment", "reply", "review", "post", "body", "subject", "to", "recipient"],
        "A field whose name or label holds one of these is a message box",
    )


class TaskLimits(Section):
    max_chars: int = setting(2000, "The longest task `browser_begin_task` takes")
    max_sites: int = setting(20, "The most sites it takes")


class Incoming(Section):
    unseen_text: bool = setting(True, "Leave out text a person cannot see")
    min_opacity: float = setting(0.05, "Text at or below this opacity is unseen")
    min_font_px: float = setting(3, "Text in a smaller font is unseen")
    min_contrast: float = setting(1.15, "Text whose colour is this close to its background is unseen")
    contrast: bool = setting(True, "The colour test. Off when the snapshot's budget does not allow it")
    screen_reader_max_chars: int = setting(
        200, "Text that is only clipped, as sites do for screen readers, is kept up to this length"
    )
    strip_invisible: bool = setting(True, "Take out characters nobody can see")
    hidden_message_chars: int = setting(8, "So many such characters in one result are a hidden message")
    fragment_max_chars: int = setting(64, "The longest end of an address, after `#`, that is shown")
    query_value_max_chars: int = setting(120, "The longest value in an address's query that is shown")
    mark_page_text: bool = setting(True, "Put what a page wrote between marks in every result")
    name_chars: int = setting(80, "How much of a name a page wrote is shown inside one of the engine's lines")
    scan: Literal["off", "local", "local_then_model"] = setting(
        "local_then_model",
        "Read page text for planted instructions: not at all, by fixed rules, or by fixed rules and "
        "then a model for what they flag",
    )
    max_passages: int = setting(5, "The most passages of one result that go to the model")
    passage_chars: int = setting(600, "The longest passage")


class Outgoing(Section):
    grouped_number_digits: int = setting(
        10, "A number written in groups counts as a secret from this many digits on: a phone, a card"
    )
    sensitive_fields: bool = setting(True, "Ask before typing a password, a card number or a code")
    sensitive_words: dict[str, list[str]] = setting(
        {
            "password": ["password", "passcode", "passphrase"],
            "card": ["card number", "cvv", "cvc", "security code"],
            "code": ["one-time code", "verification code", "otp", "pin", "mpin", "upi pin", "atm pin"],
            "identity": [
                "social security",
                "ssn",
                "aadhaar",
                "aadhar",
                "pan number",
                "pan card",
                "iban",
                "routing number",
                "account number",
            ],
        },
        "A field whose name or label holds one of these, as whole words, is sensitive. By kind",
    )
    cross_site_text: bool = setting(True, "Notice text that was read on one site and goes to another")
    min_chars: int = setting(24, "The shortest copied text that counts")
    run_chars: int = setting(12, "The length of the runs a copy is found by")
    filter_bits: int = setting(1_048_576, "The size of the memory of one site, in bits")
    filter_hashes: int = setting(4, "How many places of that memory one run marks")
    remember_chars_per_site: int = setting(250_000, "After so much text a site's memory begins again")
    remember_sites: int = setting(16, "The most sites remembered, the newest kept")
    secrets_per_site: int = setting(2000, "The most short secrets remembered for one site")
    decode_min_chars: int = setting(8, "The shortest run of Base64 or hexadecimal that is unpacked")
    question_chars: int = setting(300, "How much of the text that would leave the person is shown")
    long_address_chars: int = setting(200, "An address whose path and query are longer than this is long")
    grant_access: bool = setting(True, "Ask before agreeing to give an app access to an account")
    consent_texts: int = setting(
        40, "How many headings and buttons of a page are read to tell a screen that gives an app access"
    )
    consent_addresses: list[str] = setting(
        [
            "accounts.google.com/o/oauth2/*",
            "accounts.google.com/signin/oauth*",
            "login.microsoftonline.com/*/oauth2/*authorize*",
            "login.live.com/oauth20_authorize*",
            "appleid.apple.com/auth/authorize*",
            "github.com/login/oauth/authorize*",
            "www.facebook.com/*dialog/oauth*",
            "slack.com/oauth/*",
            "*.okta.com/oauth2/*",
            "*.auth0.com/authorize*",
        ],
        "Where the screens are on which an app is given access: host and path, `*` for anything",
    )


class ArrivingFiles(Section):
    risky_extensions: list[str] = setting(
        [
            "exe",
            "msi",
            "msix",
            "appx",
            "bat",
            "cmd",
            "com",
            "scr",
            "pif",
            "ps1",
            "vbs",
            "js",
            "jse",
            "wsf",
            "hta",
            "lnk",
            "reg",
            "jar",
            "apk",
            "dmg",
            "pkg",
            "app",
            "deb",
            "rpm",
            "sh",
            "iso",
            "img",
            "cab",
            "docm",
            "xlsm",
            "pptm",
        ],
        "A downloaded file with one of these endings is never kept",
    )
    ask_extensions: list[str] = setting(
        ["zip", "rar", "7z", "tar", "gz", "tgz", "bz2", "xz", "html", "htm", "xhtml", "mht", "mhtml", "svg"],
        "A downloaded file with one of these endings is asked about on every backend",
    )
    first_bytes: int = setting(
        16, "How much of a file's beginning is read to tell a program from what its name says it is"
    )
    ask: Literal["own_machine", "never", "always"] = setting(
        "own_machine",
        "Which downloads a person is asked about: those on their own machine, none, or every one",
    )


class Money(Section):
    max_amount: float = setting(0, "The most one paying step may show. 0 means no cap")
    max_session_total: float = setting(0, "The most the approved paying steps of a session may add up to")
    currency: str = setting("", "The currency the caps are in, as a three-letter code. Empty means any")
    around_chars: int = setting(1500, "How much of the text around a paying control is read for an amount")


class AbuseCh(Section):
    enabled: bool = setting(False, "Ask abuse.ch whether a host or a file is known to be bad")
    key_env: str = setting("ABUSE_CH_AUTH_KEY", "The variable that holds the key for abuse.ch")
    timeout_s: int = setting(2, "Longest wait for its answer")


class Rdap(Section):
    enabled: bool = setting(False, "Ask a domain's registry when the domain was registered")
    young_days: int = setting(30, "A domain younger than this is noticed")
    timeout_s: int = setting(2, "Longest wait for its answer")


class SensitiveSites(Section):
    money: list[str] = setting(
        [
            "paypal.com",
            "stripe.com",
            "wise.com",
            "chase.com",
            "bankofamerica.com",
            "wellsfargo.com",
            "hdfcbank.com",
            "icicibank.com",
            "onlinesbi.sbi",
            "axisbank.com",
            "paytm.com",
            "phonepe.com",
            "coinbase.com",
            "binance.com",
            "zerodha.com",
        ],
        "Banks, payment services, brokers and exchanges",
    )
    identity: list[str] = setting(
        [
            "accounts.google.com",
            "myaccount.google.com",
            "login.microsoftonline.com",
            "login.live.com",
            "account.microsoft.com",
            "appleid.apple.com",
            "account.apple.com",
        ],
        "Sign-in and account pages of the large providers",
    )
    health: list[str] = setting(["healthcare.gov", "nhs.uk", "abdm.gov.in"], "Health services")
    government: list[str] = setting(
        [
            "irs.gov",
            "ssa.gov",
            "login.gov",
            "gov.uk",
            "incometax.gov.in",
            "uidai.gov.in",
            "digilocker.gov.in",
            "passportindia.gov.in",
        ],
        "Government services",
    )
    more: list[str] = setting([], "Other sites that need a person's yes: a deployment's, and a person's own")


class SiteChecks(Section):
    lookalike_min_chars: int = setting(
        5, "A name shorter than this is never measured as a look-alike, on either side"
    )
    one_edit_max_chars: int = setting(
        8, "A protected name up to this length may differ by one letter; a longer one by two"
    )
    lure_min_chars: int = setting(
        4, "A protected name shorter than this is never looked for beside a lure word"
    )
    measured_hosts: int = setting(
        256, "How many hosts are remembered as measured against the protected names"
    )
    lookalike: bool = setting(True, "Notice a site whose name looks like a protected name")
    mixed_script: bool = setting(True, "Notice a site whose name is written with look-alike letters")
    ip_hosts: bool = setting(True, "Notice a site that is a bare public IP address")
    protected: list[str] = setting(
        [
            "google.com",
            "gmail.com",
            "youtube.com",
            "microsoft.com",
            "outlook.com",
            "office.com",
            "apple.com",
            "icloud.com",
            "amazon.com",
            "amazon.in",
            "paypal.com",
            "facebook.com",
            "instagram.com",
            "whatsapp.com",
            "linkedin.com",
            "twitter.com",
            "netflix.com",
            "github.com",
            "dropbox.com",
            "yahoo.com",
            "adobe.com",
            "docusign.com",
            "stripe.com",
            "coinbase.com",
            "binance.com",
            "chase.com",
            "wellsfargo.com",
            "bankofamerica.com",
            "hdfcbank.com",
            "icicibank.com",
            "axisbank.com",
            "paytm.com",
            "phonepe.com",
            "flipkart.com",
            "irctc.co.in",
            "fedex.com",
        ],
        "The names a look-alike is measured against, besides the task's own sites",
    )
    lure_words: list[str] = setting(
        [
            "login",
            "signin",
            "sign-in",
            "logon",
            "secure",
            "security",
            "verify",
            "verification",
            "account",
            "update",
            "support",
            "billing",
            "payment",
            "wallet",
            "auth",
            "confirm",
            "recover",
            "unlock",
            "bank",
            "help",
        ],
        "A protected name in a host is a lure when one of these stands beside it",
    )
    common_words: list[str] = setting(
        [
            "apply",
            "ample",
            "maple",
            "goggle",
            "paypay",
            "strip",
            "stride",
            "strive",
            "stripes",
            "chose",
            "chasm",
            "cease",
            "phase",
            "chaise",
            "amazing",
            "adore",
            "abode",
            "fedora",
            "flipcart",
            "twitch",
        ],
        "Names that sit one letter from a protected name and are never taken for a look-alike",
    )
    sensitive: SensitiveSites = SensitiveSites()
    cache_s: int = setting(3600, "How long an answer about a site is kept")
    abuse_ch: AbuseCh = AbuseCh()
    rdap: Rdap = Rdap()


class Safeguards(Section):
    model: CheckModel = CheckModel()
    reviewer: ReviewerShown = ReviewerShown()
    actions: Actions = Actions()
    task: TaskLimits = TaskLimits()
    incoming: Incoming = Incoming()
    outgoing: Outgoing = Outgoing()
    downloads: ArrivingFiles = ArrivingFiles()
    money: Money = Money()
    sites: SiteChecks = SiteChecks()


class Limits(Section):
    max_calls: int = setting(500, "Tool calls in one task, or in a session with no task. 0 means no limit")
    max_task_minutes: int = setting(60, "Minutes one task may take. 0 means no limit")
    max_calls_per_minute: int = setting(120, "Tool calls in one minute. 0 means no limit")
    rate_wait_s: int = setting(10, "How long a call waits for the minute to allow it before it is refused")
    max_model_spend_usd: float = setting(
        0, "What the engine's own model calls may cost in one session, in US dollars. 0 means no limit"
    )
    max_calls_choices: list[int] = setting(
        [100, 250, 500, 1000], "The limits of steps a person may choose from in the settings screen"
    )
    extend_calls: int = setting(100, 'The steps "Allow more" adds')
    extend_minutes: int = setting(15, 'The minutes "Allow more" adds')
    repeat_notice: int = setting(3, "The same step with nothing changed: the time the agent is told")
    repeat_refuse: int = setting(6, "The same step with nothing changed: the time it is not run")
    unanswered_in_a_row: int = setting(
        3, "Questions that ran out unanswered in a row, after which further ones are refused at once"
    )
