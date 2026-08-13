from plural_cognition.collective import local_raw_calibration_v5 as v5


def test_closed_reasoning_eof_is_empty_answer() -> None:
    assistant, reasoning = v5.extract_assistant_content_v5(
        transcript=b"User:\nrepair\n\nAssistant:\n[Start thinking]\n\nreason\n[End thinking]\n\n",
        prompt=b"repair",
    )
    assert assistant == b""
    assert reasoning == b"reason\n"
