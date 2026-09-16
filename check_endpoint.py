"""
MBAX 6418 - endpoint sanity check.

Answers three questions before any real run:
  1. Is the endpoint reachable and does the key work?
  2. What model IDs does it actually serve?
  3. Does a single round-trip come back in a shape we can parse?

Written after a 404 caused by trusting the model name in the course handout
over the name the server reports. `/v1/models` is the source of truth.

Run:  python check_endpoint.py
"""

from classify import BASE_URL, MAX_TOKENS, MODEL, available_models, client


def main() -> None:
    print(f"Endpoint : {BASE_URL}")
    print(f"Configured model : {MODEL}\n")

    try:
        served = available_models()
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED to reach /v1/models: {exc}")
        print("\nCheck the base URL and the API key before going further.")
        return

    print("Models actually served:")
    for name in served:
        marker = "  <-- configured" if name == MODEL else ""
        print(f"  {name}{marker}")

    if MODEL not in served:
        print(
            f"\nMISMATCH. {MODEL!r} is not in that list, so every call will 404.\n"
            f"Edit MODEL in classify.py, or export CLASS_MODEL='{served[0]}'."
        )
        return

    print("\nModel name matches. Testing one round trip...")

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "Reply with exactly: OK"}],
        temperature=0.0,
        max_tokens=MAX_TOKENS,
    )

    message = response.choices[0].message
    content = (message.content or "").strip()
    reasoning = getattr(message, "reasoning", None)
    usage = response.usage

    print(f"  content   : {content!r}")
    print(f"  reasoning : {'present' if reasoning else 'none'}")
    if usage:
        print(f"  tokens    : prompt {usage.prompt_tokens}, completion {usage.completion_tokens}")

    if reasoning:
        print(
            "\n  Note: this is a reasoning model. Keep max_tokens generous and read\n"
            "  choices[0].message.content only, never the whole message object."
        )

    if not content:
        print(
            "\n  Empty content. The token budget was probably spent on reasoning.\n"
            "  Raise MAX_TOKENS in classify.py."
        )
    else:
        print("\nEndpoint is good. Safe to run test_one.py.")


if __name__ == "__main__":
    main()
