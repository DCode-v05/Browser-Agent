"""Secrets come from the environment or from a .env file beside where the command is run (spec 10.1)."""

from pathlib import Path

from bap_browser.env_file import apply_env_file, environment


def test_values_in_the_file_are_added_to_the_environment(tmp_path: Path) -> None:
    file = tmp_path / ".env"
    file.write_text(
        "# the model's key\n"
        "OPENAI_API_KEY=sk-from-the-file\n"
        "\n"
        "export BAP_BROWSER_TOKEN = spaced \n"
        'QUOTED="two words"\n'
        "SINGLE='it''s'\n"
        "EMPTY=\n"
        "WITH_EQUALS=a=b=c\n"
        "TRAILING=value # a note\n"
        'HASH_IN_QUOTES="a # b"\n',
        encoding="utf-8",
    )
    env = environment(file, {"PATH": "/bin"})
    assert env == {
        "PATH": "/bin",
        "OPENAI_API_KEY": "sk-from-the-file",
        "BAP_BROWSER_TOKEN": "spaced",
        "QUOTED": "two words",
        "SINGLE": "it''s",
        "EMPTY": "",
        "WITH_EQUALS": "a=b=c",
        "TRAILING": "value",
        "HASH_IN_QUOTES": "a # b",
    }


def test_what_is_already_in_the_environment_wins(tmp_path: Path) -> None:
    file = tmp_path / ".env"
    file.write_text("OPENAI_API_KEY=from-the-file\n", encoding="utf-8")
    assert environment(file, {"OPENAI_API_KEY": "from-the-shell"})["OPENAI_API_KEY"] == "from-the-shell"


def test_no_file_means_the_environment_as_it_is(tmp_path: Path) -> None:
    given = {"A": "1"}
    assert environment(tmp_path / ".env", given) == {"A": "1"}
    assert environment(tmp_path / ".env", given) is not given


def test_lines_that_are_not_settings_are_passed_over(tmp_path: Path) -> None:
    file = tmp_path / ".env"
    file.write_text("just words\n=no name\n1BAD=x\nGOOD=1\n\ufeffBOM=2\n", encoding="utf-8")
    assert environment(file, {}) == {"GOOD": "1"}


def test_a_file_saved_with_a_byte_order_mark_is_read(tmp_path: Path) -> None:
    file = tmp_path / ".env"
    file.write_bytes(b"\xef\xbb\xbfOPENAI_API_KEY=sk-with-a-mark\r\nOTHER=1\r\n")
    assert environment(file, {}) == {"OPENAI_API_KEY": "sk-with-a-mark", "OTHER": "1"}


def test_the_files_settings_become_part_of_the_environment_every_part_of_the_program_reads(
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text("BAP_BROWSER_PROXY_USERNAME=ada\nPATH=overwritten\n", encoding="utf-8")
    environ = {"PATH": "/bin"}
    apply_env_file(tmp_path / ".env", environ)
    assert environ == {"PATH": "/bin", "BAP_BROWSER_PROXY_USERNAME": "ada"}
