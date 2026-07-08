import re

# Pre-compiled regex patterns for sensitive information
SENSITIVE_PATTERNS = {
    "EMAIL": re.compile(
        r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b",
        re.IGNORECASE
    ),
    "PHONE": re.compile(
        r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
    ),
    "CREDIT_CARD": re.compile(
        r"\b(?:\d{4}[-\s]?){3}\d{1,4}\b|\b\d{13,16}\b"
    ),
    "SSN": re.compile(
        r"\b\d{3}-\d{2}-\d{4}\b"
    ),
    "API_KEY": re.compile(
        r"\b(?:sk-[a-zA-Z0-9]{20,}|bearer\s+[a-zA-Z0-9_\-\.\+]{15,}|(?:api_key|apikey|secret|password|private_key|token|auth_token)\b\s*[:=]\s*['\"a-zA-Z0-9_\-\.]{10,})\b",
        re.IGNORECASE
    ),
    "IP_ADDRESS": re.compile(
        r"\b(?:(?:[0-9]{1,3}\.){3}[0-9]{1,3}|(?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4})\b"
    )
}

def redact_sensitive_info(text: str) -> tuple[str, list[str]]:
    """
    Scans the text using regex patterns and replaces sensitive information with redacted placeholders.
    
    Args:
        text (str): The text to scan and redact.
        
    Returns:
        tuple[str, list[str]]: The redacted text and a list of types of sensitive information that were redacted.
    """
    if not text:
        return text, []

    redacted_text = text
    redacted_types = []
    
    for label, pattern in SENSITIVE_PATTERNS.items():
        if pattern.search(redacted_text):
            redacted_text = pattern.sub(f"[{label}_REDACTED]", redacted_text)
            redacted_types.append(label)
            
    return redacted_text, redacted_types

if __name__ == "__main__":
    # Small local sanity check/test for redactor
    test_text = (
        "Hello, my email is user.name+test@example.co.uk and my phone is +1-555-019-2834.\n"
        "Do not tell anyone my api_key = 'sk-abcdef1234567890abcdef123456' or secret:password123!\n"
        "Here are my cards: 4111-2222-3333-4444 and my SSN 000-12-3456.\n"
        "I am connecting from 192.168.1.100."
    )
    print("Original text:\n", test_text, "\n")
    redacted, types = redact_sensitive_info(test_text)
    print("Redacted text:\n", redacted, "\n")
    print("Redacted types:", types)
