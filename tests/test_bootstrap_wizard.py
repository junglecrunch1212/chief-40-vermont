from pathlib import Path

from pib.bootstrap_wizard import parse_env_file, upsert_env_value, wizard_state


def test_upsert_and_parse_env(tmp_path, monkeypatch):
    env_file = tmp_path / '.env'
    monkeypatch.setenv('PIB_ENV_FILE', str(env_file))

    upsert_env_value('ANTHROPIC_API_KEY', 'abc123', path=env_file)
    upsert_env_value('TWILIO_AUTH_TOKEN', 'tok456', path=env_file)
    upsert_env_value('ANTHROPIC_API_KEY', 'abc999', path=env_file)

    parsed = parse_env_file(env_file)
    assert parsed['ANTHROPIC_API_KEY'] == 'abc999'
    assert parsed['TWILIO_AUTH_TOKEN'] == 'tok456'


def test_wizard_state_marks_missing_required(tmp_path, monkeypatch):
    env_file = tmp_path / '.env'
    monkeypatch.setenv('PIB_ENV_FILE', str(env_file))

    # Set only one required key, others should remain missing.
    upsert_env_value('ANTHROPIC_API_KEY', 'sk-ant-123456', path=env_file)

    state = wizard_state()
    assert state['complete'] is False
    assert 'ANTHROPIC_API_KEY' not in state['missing_required']
    assert 'TWILIO_AUTH_TOKEN' in state['missing_required']
