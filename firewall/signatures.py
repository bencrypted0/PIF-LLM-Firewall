import re
import unicodedata
import base64

# Leetspeak translation map
LEET_MAP = str.maketrans("4310@$71!", "aeioastiI")

# Pattern lists
INJECTION_PATTERNS = [
    r"ignore (all|previous|prior|the above)\s*(instructions|prompts|rules)",
    r"(disregard|forget|discard)\s+(all|previous|prior)\s+(instructions|context|rules)",
    r"you (are|will be)\s+now\s+(a|an)\s+\w+.*\b(unrestricted|no rules|jailbroken)\b",
    r"act as\s+(if\s+)?(you have no|there are no)\s+(restrictions|filters|rules)",
    r"(system|developer)\s*(prompt|override|mode)\s*(:|=|is)",
    r"\bdan\b.*\bmode\b",
    r"pretend (you('re| are)|to be)\s+.*(unfiltered|unrestricted|no rules)",
]

ROLE_HIJACK_PATTERNS = [
    r"(you are|act as|pretend to be|roleplay(\s+as)?|respond\s+as)\s+.*(no (rules|filters|restrictions)|unrestricted|uncensored|jailbroken)",
    r"from now on,?\s+you (will|must|shall)\s+(ignore|bypass|disregard)",
    r"this is a (hypothetical|fictional)\s+scenario.*(no (rules|restrictions|guidelines))",
]

DELIMITER_PATTERNS = [
    r"\[/?system\]|/system",  # Safer version of r"\[?/?system\]?" to prevent false positives on plain word "system"
    r"<\|.*?\|>", 
    r"###\s*(system|instruction)",
    r"\[INST\]", 
    r"<<SYS>>",
]

# Compile patterns for efficiency
compiled_injections = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]
compiled_role_hijack = [re.compile(p, re.IGNORECASE) for p in ROLE_HIJACK_PATTERNS]
compiled_delimiters = [re.compile(p, re.IGNORECASE) for p in DELIMITER_PATTERNS]


def deleet(text: str) -> str:
    """Translates leetspeak characters back to standard English."""
    return text.translate(LEET_MAP)


def normalize(text: str) -> str:
    """Collapses unicode homoglyphs, strips invisible characters, and normalizes separators."""
    text = unicodedata.normalize("NFKC", text)
    text = text.encode("ascii", "ignore").decode()
    text = re.sub(r'[\s\-_.,!*]+', ' ', text.lower())
    return text.strip()


def detect_signatures(text: str) -> tuple[bool, str]:
    """
    Scans input text for prompt injection signatures, roleplay hijacks,
    delimiter faking, and base64 encoded payloads.
    
    Returns:
        (is_injection, reason)
    """
    # 1. Check raw text for delimiters first (before normalization alters special characters)
    for pattern in compiled_delimiters:
        if pattern.search(text):
            return True, f"Delimiter/Injection-Marker Match ({pattern.pattern})"

    # 2. Preprocess text (De-leet and Normalize)
    cleaned_text = normalize(deleet(text))

    # 3. Check standard injection patterns
    for pattern in compiled_injections:
        if pattern.search(cleaned_text):
            return True, f"Injection Pattern Match ({pattern.pattern})"

    # 4. Check role-play / persona hijack patterns
    for pattern in compiled_role_hijack:
        if pattern.search(cleaned_text):
            return True, f"Role-play/Persona Hijack Match ({pattern.pattern})"

    # 5. Check for base64 encoded payloads recursively
    # Matches base64 looking strings that are at least 20 characters long
    b64_pattern = re.compile(r'[A-Za-z0-9+/]{20,}={0,2}')
    for match in b64_pattern.findall(text):
        try:
            decoded = base64.b64decode(match).decode('utf-8', errors='ignore')
            is_inj, reason = detect_signatures(decoded)
            if is_inj:
                return True, f"Base64 Encoded Payload -> {reason}"
        except Exception:
            continue

    return False, "Clean"
